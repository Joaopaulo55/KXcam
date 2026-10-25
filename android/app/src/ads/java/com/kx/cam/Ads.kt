package com.kx.cam
import android.app.Activity
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.View
import android.view.ViewGroup
import com.appodeal.ads.Appodeal
import com.appodeal.ads.initializing.ApdInitializationCallback
import com.appodeal.ads.initializing.ApdInitializationError

/** Versão com Appodeal (flavor "ads"): banner + intersticial + vídeo premiado. O Appodeal escolhe a rede. */
object Ads {
    val enabled get() = BuildConfig.APPODEAL_KEY.isNotEmpty()
    @Volatile private var ready = false
    @Volatile private var initErr = ""
    private var bannerShown = false
    private var lastInter = 0L
    private var noAdsUntil = 0L
    private val h = Handler(Looper.getMainLooper())
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
                    // Erros aqui costumam ser de UMA rede; o SDK continua a funcionar com as outras.
                    initErr = errors?.joinToString(" | ") { it.toString() }?.take(220) ?: ""
                    ready = true
                    a.runOnUiThread {
                        box.removeAllViews(); box.addView(Appodeal.getBannerView(a))
                        showBanner(a, 0)
                    }
                }
            })
    }

    /** O banner só mostra quando já há anúncio carregado: tenta de novo a cada 3 s. */
    private fun showBanner(a: Activity, tries: Int) {
        if (bannerShown || tries > 80) return
        if (SystemClock.elapsedRealtime() >= noAdsUntil && Appodeal.show(a, Appodeal.BANNER_VIEW)) bannerShown = true
        else h.postDelayed({ showBanner(a, tries + 1) }, 3000)
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

    /** Linha de diagnóstico mostrada no ecrã do app. */
    fun status(): String {
        if (!enabled) return "Anúncios desativados (sem chave)"
        if (!ready) return "Appodeal: a iniciar..."
        fun ok(t: Int) = if (Appodeal.isLoaded(t)) "OK" else "a carregar"
        return "Appodeal: SDK pronto | banner ${ok(Appodeal.BANNER)} | vídeo ${ok(Appodeal.REWARDED_VIDEO)} | interst. ${ok(Appodeal.INTERSTITIAL)}" +
            (if (initErr.isNotEmpty()) "\nAvisos: $initErr" else "")
    }
}
