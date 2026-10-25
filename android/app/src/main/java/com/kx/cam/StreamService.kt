package com.kx.cam

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager.PERMISSION_GRANTED
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.Matrix
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.PowerManager
import android.os.SystemClock
import android.util.Size
import androidx.camera.core.*
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleService
import java.io.*
import java.net.ServerSocket
import java.net.Socket
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

// KX Cam - servidor MJPEG (/video), PCM 16kHz (/audio) e controlo (/cmd)
class StreamService : LifecycleService() {
    companion object { const val PORT = 4747; @Volatile var running = false }

    private var server: ServerSocket? = null
    private val lock = java.lang.Object()
    @Volatile private var frame: ByteArray? = null
    private var seq = 0L
    private val viewers = AtomicInteger()
    private val audioOut = mutableListOf<OutputStream>()
    @Volatile private var front = false
    @Volatile private var torch = false
    @Volatile private var zoom = 0f
    @Volatile private var ev = 0f
    @Volatile private var quality = 80
    @Volatile private var height = 720
    @Volatile private var fps = 30
    @Volatile private var mic = true
    private var camera: Camera? = null
    private var lastTs = 0L
    private val exec = Executors.newSingleThreadExecutor()
    private var wl: PowerManager.WakeLock? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        if (running) return START_STICKY
        if (checkSelfPermission(android.Manifest.permission.CAMERA) != PERMISSION_GRANTED) { stopSelf(); return START_NOT_STICKY }
        val hasMic = checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) == PERMISSION_GRANTED
        getSystemService(NotificationManager::class.java)
            .createNotificationChannel(NotificationChannel("kx", "KX Cam", NotificationManager.IMPORTANCE_LOW))
        val n = Notification.Builder(this, "kx").setContentTitle("KX Cam").setContentText("A transmitir na porta $PORT")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setContentIntent(PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)).build()
        if (Build.VERSION.SDK_INT >= 29) {
            var t = ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA
            if (hasMic) t = t or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
            startForeground(1, n, t)
        } else startForeground(1, n)
        running = true
        wl = (getSystemService(POWER_SERVICE) as PowerManager).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "kx:cam").also { it.acquire() }
        Thread { serve() }.start()
        if (hasMic) Thread { audioLoop() }.start()
        bind()
        return START_STICKY
    }

    // ---------- câmara ----------
    private fun bind() {
        val f = ProcessCameraProvider.getInstance(this)
        f.addListener({
            val p = f.get(); p.unbindAll()
            val rs = ResolutionSelector.Builder().setResolutionStrategy(
                ResolutionStrategy(Size(height * 16 / 9, height), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER)).build()
            val ia = ImageAnalysis.Builder().setResolutionSelector(rs)
                .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            ia.setAnalyzer(exec) { onFrame(it) }
            val sel = if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
            camera = p.bindToLifecycle(this, sel, ia)
            applyCtl()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun applyCtl() {
        val c = camera ?: return
        c.cameraControl.enableTorch(torch)
        c.cameraControl.setLinearZoom(zoom)
        val r = c.cameraInfo.exposureState.exposureCompensationRange
        if (r.upper != 0 || r.lower != 0)
            c.cameraControl.setExposureCompensationIndex((if (ev >= 0) ev * r.upper else -ev * r.lower).toInt())
    }

    private fun focusCenter() {
        val c = camera ?: return
        val pt = SurfaceOrientedMeteringPointFactory(1f, 1f).createPoint(0.5f, 0.5f)
        c.cameraControl.startFocusAndMetering(FocusMeteringAction.Builder(pt).build())
    }

    private fun onFrame(img: ImageProxy) {
        try {
            val now = SystemClock.elapsedRealtime()
            if (viewers.get() == 0 || now - lastTs < 1000L / fps) return
            lastTs = now
            var bmp = img.toBitmap()
            val r = img.imageInfo.rotationDegrees
            if (r != 0) bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, Matrix().apply { postRotate(r.toFloat()) }, true)
            val bo = ByteArrayOutputStream(1 shl 17)
            bmp.compress(Bitmap.CompressFormat.JPEG, quality, bo)
            synchronized(lock) { frame = bo.toByteArray(); seq++; lock.notifyAll() }
        } finally { img.close() }
    }

    // ---------- áudio ----------
    @SuppressLint("MissingPermission")
    private fun audioLoop() {
        val rate = 16000
        val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val ar = AudioRecord(MediaRecorder.AudioSource.MIC, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, min * 2)
        ar.startRecording()
        val b = ByteArray(3200)
        while (running) {
            val n = ar.read(b, 0, b.size)
            if (n <= 0 || !mic) continue
            synchronized(audioOut) {
                val i = audioOut.iterator()
                while (i.hasNext()) try { i.next().write(b, 0, n) } catch (e: Exception) { i.remove() }
            }
        }
        ar.stop(); ar.release()
    }

    // ---------- servidor ----------
    private fun serve() {
        try {
            server = ServerSocket(PORT)
            while (running) { val s = server!!.accept(); Thread { handle(s) }.start() }
        } catch (_: Exception) {}
    }

    private fun handle(s: Socket) {
        try {
            s.tcpNoDelay = true
            val br = BufferedReader(InputStreamReader(s.getInputStream()))
            val line = br.readLine() ?: return
            while (true) { val h = br.readLine(); if (h.isNullOrEmpty()) break }
            val target = line.split(" ").getOrElse(1) { "/" }
            val out = s.getOutputStream()
            when (target.substringBefore("?")) {
                "/video" -> video(s, out)
                "/audio" -> audio(s, out)
                "/cmd" -> { cmd(target.substringAfter("?", "")); reply(out, "OK") }
                else -> reply(out, "KXCam")
            }
        } catch (_: Exception) {} finally { try { s.close() } catch (_: Exception) {} }
    }

    private fun reply(out: OutputStream, t: String) {
        val b = t.toByteArray()
        out.write("HTTP/1.1 200 OK\r\nContent-Length: ${b.size}\r\nConnection: close\r\n\r\n".toByteArray()); out.write(b); out.flush()
    }

    private fun video(s: Socket, out: OutputStream) {
        out.write("HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=kx\r\nCache-Control: no-cache\r\n\r\n".toByteArray())
        viewers.incrementAndGet()
        var last = 0L
        try {
            while (running && !s.isClosed) {
                val f = synchronized(lock) { while (seq == last && running) lock.wait(1000); last = seq; frame }
                val b = f ?: continue
                out.write("--kx\r\nContent-Type: image/jpeg\r\nContent-Length: ${b.size}\r\n\r\n".toByteArray())
                out.write(b); out.write("\r\n".toByteArray()); out.flush()
            }
        } finally { viewers.decrementAndGet() }
    }

    private fun audio(s: Socket, out: OutputStream) {
        out.write("HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\n\r\n".toByteArray()); out.flush()
        synchronized(audioOut) { audioOut.add(out) }
        while (running && !s.isClosed && synchronized(audioOut) { audioOut.contains(out) }) Thread.sleep(300)
    }

    private fun cmd(q: String) {
        val m = q.split("&").filter { it.contains("=") }.associate { it.substringBefore("=") to it.substringAfter("=") }
        var rebind = false
        m["cam"]?.let { val f = it == "front"; if (f != front) { front = f; rebind = true } }
        m["res"]?.toIntOrNull()?.let { if (it != height) { height = it; rebind = true } }
        m["q"]?.toIntOrNull()?.let { quality = it.coerceIn(20, 100) }
        m["fps"]?.toIntOrNull()?.let { fps = it.coerceIn(5, 60) }
        m["mic"]?.let { mic = it == "1" }
        m["torch"]?.let { torch = it == "1" }
        m["zoom"]?.toFloatOrNull()?.let { zoom = it.coerceIn(0f, 1f) }
        m["ev"]?.toFloatOrNull()?.let { ev = it.coerceIn(-1f, 1f) }
        val focus = m.containsKey("focus")
        ContextCompat.getMainExecutor(this).execute { if (rebind) bind() else applyCtl(); if (focus) focusCenter() }
    }

    override fun onDestroy() {
        running = false
        try { server?.close() } catch (_: Exception) {}
        try { ProcessCameraProvider.getInstance(this).get().unbindAll() } catch (_: Exception) {}
        synchronized(lock) { lock.notifyAll() }
        wl?.let { if (it.isHeld) it.release() }
        exec.shutdown()
        super.onDestroy()
    }
}
