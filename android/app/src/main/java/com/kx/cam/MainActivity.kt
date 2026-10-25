package com.kx.cam

import android.Manifest.permission.*
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager.PERMISSION_GRANTED
import android.graphics.Color
import android.graphics.Typeface
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.widget.*
import androidx.core.content.ContextCompat
import java.net.NetworkInterface

// KX Cam - by João Francisco Vica Paulo
class MainActivity : Activity() {
    private lateinit var info: TextView
    private lateinit var btn: Button
    private lateinit var black: View

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setPadding(48, 48, 48, 48) }
        fun tv(t: String, sp: Float, c: Int, bold: Boolean = false) = TextView(this).apply {
            text = t; textSize = sp; setTextColor(c); gravity = Gravity.CENTER; setPadding(0, 8, 0, 8)
            if (bold) setTypeface(null, Typeface.BOLD)
        }
        col.addView(ImageView(this).apply { setImageResource(R.mipmap.ic_launcher) }, LinearLayout.LayoutParams(300, 300))
        col.addView(tv("KX Cam", 32f, Color.WHITE, true))
        col.addView(tv("by João Francisco Vica Paulo", 14f, 0xFF22D3EE.toInt()))
        info = tv("", 16f, 0xFFCBD5E1.toInt()); col.addView(info)
        btn = Button(this).apply { setOnClickListener { toggle() } }; col.addView(btn)
        col.addView(Button(this).apply { text = "Ecrã preto (poupar bateria)"; setOnClickListener { setBlack(true) } })
        black = View(this).apply { setBackgroundColor(Color.BLACK); visibility = View.GONE; setOnClickListener { setBlack(false) } }
        setContentView(FrameLayout(this).apply { setBackgroundColor(0xFF0B1220.toInt()); addView(col); addView(black) })
        if (intent.getBooleanExtra("autostart", false) && !StreamService.running) start()
    }

    override fun onResume() { super.onResume(); refresh() }

    private fun setBlack(on: Boolean) {
        black.visibility = if (on) View.VISIBLE else View.GONE
        window.attributes = window.attributes.apply { screenBrightness = if (on) 0f else -1f }
    }

    private fun toggle() {
        if (StreamService.running) { stopService(Intent(this, StreamService::class.java)); info.postDelayed({ refresh() }, 600) }
        else start()
    }

    private fun start() {
        val need = mutableListOf(CAMERA, RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= 33) need.add(POST_NOTIFICATIONS)
        val miss = need.filter { checkSelfPermission(it) != PERMISSION_GRANTED }
        if (miss.isNotEmpty()) requestPermissions(miss.toTypedArray(), 1) else go()
    }

    override fun onRequestPermissionsResult(rc: Int, p: Array<out String>, r: IntArray) {
        super.onRequestPermissionsResult(rc, p, r)
        if (checkSelfPermission(CAMERA) == PERMISSION_GRANTED) go()
        else Toast.makeText(this, "Permissão da câmara necessária", Toast.LENGTH_LONG).show()
    }

    private fun go() {
        ContextCompat.startForegroundService(this, Intent(this, StreamService::class.java))
        info.postDelayed({ refresh() }, 800)
    }

    private fun refresh() {
        val on = StreamService.running
        btn.text = if (on) "PARAR" else "INICIAR"
        info.text = "Wi-Fi: ${ip()}:${StreamService.PORT}\nUSB: ligue o cabo (Depuração USB) e use o KX Cam no PC\n\n" +
            (if (on) "● A TRANSMITIR" else "● Parado")
    }

    private fun ip(): String = try {
        NetworkInterface.getNetworkInterfaces().toList().flatMap { it.inetAddresses.toList() }
            .firstOrNull { !it.isLoopbackAddress && it.address.size == 4 }?.hostAddress ?: "—"
    } catch (e: Exception) { "—" }
}
