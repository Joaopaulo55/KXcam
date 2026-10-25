package com.kx.cam
import android.app.Activity
import android.os.SystemClock
import android.view.View
import android.view.ViewGroup
import com.appodeal.ads.Appodeal
import com.appodeal.ads.initializing.ApdInitializationCallback
import com.appodeal.ads.initializing.ApdInitializationError

/** Versão com Appodeal (flavor "ads"): banner + intersticial + vídeo premiado. O Appodeal escolhe a rede. */
object Ads {
    val enabled get() = BuildConfig.APPODEAL_KEY.isNotEmpty()
    private var ready = false
    private var lastInter = 0L
    private var noAdsUntil = 0L
    private const val MIN_GAP_MS = 180_000L        // máx. 1 intersticial a cada 3 min
    private const val REWARD_MS = 30 * 60_000L     // vídeo premiado = 30 min sem banner/intersticial

    fun init(a: Activity, box: ViewGroup) {
        if (!enabled) { box.visibility = View.GONE; return }
        if (BuildConfig.ADS_TEST) Appodeal.setTesting(true)
        lastInter = SystemClock.elapsedRealtime()
        Appodeal.initialize(a, BuildConfig.APPODEAL_KEY,
            Appodeal.BANNER or Appodeal.INTERSTITIAL or Appodeal.REWARDED_VIDEO,
            object : ApdInitializationCallback {
                override fun onInitializationFinished(errors: List<ApdInitializationError>?) {
                    ready = errors.isNullOrEmpty()
                    if (ready) a.runOnUiThread {
                        box.removeAllViews(); box.addView(Appodeal.getBannerView(a))
                        Appodeal.show(a, Appodeal.BANNER_VIEW)
                    }
                }
            })
    }

    fun onResume(box: ViewGroup) {
        box.visibility = if (!enabled || SystemClock.elapsedRealtime() < noAdsUntil) View.GONE else View.VISIBLE
    }

    fun interstitial(a: Activity) {
        val now = SystemClock.elapsedRealtime()
        if (!ready || now < noAdsUntil || now - lastInter < MIN_GAP_MS) return
        if (Appodeal.isLoaded(Appodeal.INTERSTITIAL)) { lastInter = now; Appodeal.show(a, Appodeal.INTERSTITIAL) }
    }

    /** Botão "Apoiar": mostra vídeo premiado; recompensa = 30 min sem anúncios. */
    fun rewarded(a: Activity, box: ViewGroup): Boolean {
        if (!ready || !Appodeal.isLoaded(Appodeal.REWARDED_VIDEO)) return false
        val shown = Appodeal.show(a, Appodeal.REWARDED_VIDEO)
        if (shown) { noAdsUntil = SystemClock.elapsedRealtime() + REWARD_MS; box.visibility = View.GONE }
        return shown
    }
}
