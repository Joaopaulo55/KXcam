plugins { id("com.android.application"); id("org.jetbrains.kotlin.android") }

android {
    namespace = "com.kx.cam"
    compileSdk = 34
    defaultConfig { applicationId = "com.kx.cam"; minSdk = 26; targetSdk = 34; versionCode = 2; versionName = "2.0" }
    buildFeatures { buildConfig = true }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    flavorDimensions += "mon"
    productFlavors {
        // lite = sem anúncios (sempre compila) | ads = com Appodeal
        create("lite") { dimension = "mon"
            buildConfigField("String", "APPODEAL_KEY", "\"\""); buildConfigField("boolean", "ADS_TEST", "true") }
        create("ads") { dimension = "mon"
            buildConfigField("String", "APPODEAL_KEY", "\"${System.getenv("APPODEAL_KEY") ?: "6e5d4f0e9a8f6b365f5488f3ac3a726e54eaec43b20162d7"}\"")
            // ADS_LIVE=1 (só no build final da Play Store) desliga o modo de teste
            buildConfigField("boolean", "ADS_TEST", if (System.getenv("ADS_LIVE") == "1") "false" else "true")
            manifestPlaceholders["admobAppId"] = System.getenv("ADMOB_APP_ID") ?: "ca-app-pub-3940256099942544~3347511713"
        }
    }
}

dependencies {
    val cx = "1.3.4"
    implementation("androidx.camera:camera-core:$cx")
    implementation("androidx.camera:camera-camera2:$cx")
    implementation("androidx.camera:camera-lifecycle:$cx")
    implementation("androidx.lifecycle:lifecycle-service:2.8.4")
    implementation("androidx.core:core-ktx:1.13.1")

    // Appodeal: cole em appodeal-adapters.txt as linhas geradas em
    // docs.appodeal.com/android/advanced/configure-mediated-networks (qualquer formato; só as coordenadas são lidas)
    val f = file("appodeal-adapters.txt")
    if (f.exists()) Regex("""["']([\w.\-]+:[\w.\-]+:[\w.\-]+)["']""").findAll(f.readText())
        .forEach { "adsImplementation"(it.groupValues[1]) }
}
