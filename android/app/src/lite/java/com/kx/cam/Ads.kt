package com.kx.cam
import android.app.Activity
import android.view.View
import android.view.ViewGroup

/** Versão sem anúncios (flavor "lite"). */
object Ads {
    val enabled = false
    fun init(a: Activity, box: ViewGroup) { box.visibility = View.GONE }
    fun onResume(box: ViewGroup) { box.visibility = View.GONE }
    fun interstitial(a: Activity) {}
    fun rewarded(a: Activity, box: ViewGroup): Boolean = false
    fun status(): String = ""
}
