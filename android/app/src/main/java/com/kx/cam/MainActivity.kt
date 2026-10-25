package com.kx.cam

import android.Manifest.permission.*
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager.PERMISSION_GRANTED
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
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
    private lateinit var state: TextView
    private lateinit var btn: Button
    private lateinit var black: View
    private lateinit var adBox: FrameLayout
    private lateinit var adInfo: TextView
    private val tick = object : Runnable { override fun run() { adInfo.text = Ads.status(); adInfo.postDelayed(this, 2000) } }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setPadding(48, 48, 48, 160) }
        fun tv(t: String, sp: Float, c: Int, bold: Boolean = false) = TextView(this).apply {
            text = t; textSize = sp; setTextColor(c); gravity = Gravity.CENTER; setPadding(0, 8, 0, 8)
            if (bold) setTypeface(null, Typeface.BOLD)
        }
        fun pill(c: Int) = GradientDrawable().apply { cornerRadius = 80f; setColor(c) }
        col.addView(ImageView(this).apply { setImageResource(R.mipmap.ic_launcher) }, LinearLayout.LayoutParams(280, 280))
        col.addView(tv("KX Cam", 32f, Color.WHITE, true))
        col.addView(tv("by João Francisco Vica Paulo", 14f, 0xFF22D3EE.toInt()))
        state = tv("", 15f, Color.WHITE, true); col.addView(state)
        info = tv("", 15f, 0xFFCBD5E1.toInt()); col.addView(info)
        btn = Button(this).apply { setTextColor(Color.WHITE); setOnClickListener { toggle() } }
        col.addView(btn, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 150).apply { topMargin = 24 })
        col.addView(Button(this).apply { text = "Ecrã preto (poupar bateria)"; background = pill(0xFF1E293B.toInt()); setTextColor(Color.WHITE); setOnClickListener { setBlack(true) } },
            LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 130).apply { topMargin = 16 })
        if (Ads.enabled) col.addView(Button(this).apply { text = "♥ Apoiar o KX Cam: ver vídeo (30 min sem anúncios)"; background = pill(0xFF7C3AED.toInt()); setTextColor(Color.WHITE)
            setOnClickListener { if (!Ads.rewarded(this@MainActivity, adBox)) Toast.makeText(this@MainActivity, "Vídeo ainda a carregar.\n" + Ads.status(), Toast.LENGTH_SHORT).show() } },
            LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 130).apply { topMargin = 16 })
        adInfo = tv("", 11f, 0xFF64748B.toInt()); col.addView(adInfo)
        adBox = FrameLayout(this)
        black = View(this).apply { setBackgroundColor(Color.BLACK); visibility = View.GONE; setOnClickListener { setBlack(false) } }
        setContentView(FrameLayout(this).apply {
            setBackgroundColor(0xFF0B1220.toInt()); addView(col)
            addView(adBox, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM))
            addView(black)
        })
        Ads.init(this, adBox)
        if (intent.getBooleanExtra("autostart", false) && !StreamService.running) start()
    }

    override fun onResume() { super.onResume(); refresh(); Ads.onResume(adBox); adInfo.post(tick) }
    override fun onPause() { super.onPause(); adInfo.removeCallbacks(tick) }

    private fun setBlack(on: Boolean) {
        black.visibility = if (on) View.VISIBLE else View.GONE
        if (on) adBox.visibility = View.GONE else Ads.onResume(adBox)
        window.attributes = window.attributes.apply { screenBrightness = if (on) 0f else -1f }
    }

    private fun toggle() {
        if (StreamService.running) {
            stopService(Intent(this, StreamService::class.java))
            info.postDelayed({ refresh(); Ads.interstitial(this) }, 700)
        } else start()
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
        btn.background = GradientDrawable().apply { cornerRadius = 80f; setColor(if (on) 0xFFDC2626.toInt() else 0xFF2563EB.toInt()) }
        state.text = if (on) "● A TRANSMITIR" else "● Parado"
        state.setTextColor(if (on) 0xFF4ADE80.toInt() else 0xFF94A3B8.toInt())
        info.text = "Wi-Fi: ${ip()}:${StreamService.PORT}\nUSB: ligue o cabo (Depuração USB) e use o KX Cam no PC"
    }

    private fun ip(): String = try {
        NetworkInterface.getNetworkInterfaces().toList().flatMap { it.inetAddresses.toList() }
            .firstOrNull { !it.isLoopbackAddress && it.address.size == 4 }?.hostAddress ?: "—"
    } catch (e: Exception) { "—" }
}
