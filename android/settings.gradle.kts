pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement {
    repositories {
        google(); mavenCentral()
        // Repositório do Appodeal (confirme o URL no gerador: docs.appodeal.com > Configure Mediated Networks)
        maven { url = uri("https://artifactory.appodeal.com/appodeal") }
    }
}
rootProject.name = "KXCam"
include(":app")
