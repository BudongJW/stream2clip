package io.github.budongjw.stream2clip

import android.app.Application

/** Starts the app's Python in the background: the first start unpacks it (several seconds), the screen does not wait. */
class S2cApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Thread({ Core.start(this) }, "python-start").start()
    }
}
