plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

// The app's version is the Python package's (src/stream2clip/__init__.py): one release number for both.
// versionCode grows with it (0.18.0 -> 18000), so a newer release installs over an older one.
val packageVersion: String = Regex("""__version__ = "([^"]+)"""")
    .find(rootProject.file("../src/stream2clip/__init__.py").readText())!!.groupValues[1]
val versionParts = packageVersion.split(".").map { part -> part.takeWhile(Char::isDigit).ifEmpty { "0" }.toInt() } + listOf(0, 0, 0)

// Release APKs are signed with one fixed key, or Android refuses to install a new release over the last one.
// The key comes from the environment (the Android workflow fills it from the repository's secrets, see
// docs/ANDROID.md); without it the release APK is left unsigned and debug builds keep the debug key.
val releaseKeystore: String? = System.getenv("STREAM2CLIP_KEYSTORE")?.takeIf { it.isNotBlank() }

android {
    namespace = "io.github.budongjw.stream2clip"
    compileSdk = 36

    defaultConfig {
        applicationId = "io.github.budongjw.stream2clip"
        minSdk = 29 // Android 10: clips are saved to Movies/stream2clip without a storage permission
        targetSdk = 36
        versionCode = versionParts[0] * 1_000_000 + versionParts[1] * 1_000 + versionParts[2]
        versionName = packageVersion
        ndk {
            // Phones (arm64) and the emulator on a PC (x86_64); Chaquopy ships Python for each.
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
    }

    signingConfigs {
        if (releaseKeystore != null) {
            create("release") {
                storeFile = file(releaseKeystore)
                storePassword = System.getenv("STREAM2CLIP_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("STREAM2CLIP_KEY_ALIAS")
                keyPassword = System.getenv("STREAM2CLIP_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
    }
    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

kotlin {
    jvmToolchain(17)
}

chaquopy {
    defaultConfig {
        version = "3.13"
        pip {
            // The stream2clip core's own needs (pyproject.toml), in the versions Chaquopy builds for Android,
            // and yt-dlp, which runs inside the app: an Android app cannot start another program.
            install("numpy==1.26.2")
            install("pillow==11.0.0")
            install("yt-dlp==2026.10.26")
        }
    }
    sourceSets {
        getByName("main") {
            // The desktop app's own package, unchanged; its PySide6 windows stay on the PC.
            srcDir("../../src")
            exclude("stream2clip/gui/**")
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.10.01")
    implementation(composeBom)
    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.11.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.4")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.4")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")

    val media3 = "1.8.0"
    implementation("androidx.media3:media3-transformer:$media3")
    implementation("androidx.media3:media3-effect:$media3")
    implementation("androidx.media3:media3-common:$media3")
    implementation("androidx.media3:media3-exoplayer:$media3")
    implementation("androidx.media3:media3-exoplayer-hls:$media3")
    implementation("androidx.media3:media3-ui:$media3")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.json:json:20250517") // the real org.json: Android's is only a stub in local tests
}
