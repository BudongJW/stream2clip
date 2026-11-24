package io.github.budongjw.stream2clip

import android.content.Context
import android.opengl.GLES20
import androidx.media3.common.VideoFrameProcessingException
import androidx.media3.common.util.GlProgram
import androidx.media3.common.util.GlUtil
import androidx.media3.common.util.Size
import androidx.media3.common.util.UnstableApi
import androidx.media3.effect.BaseGlShaderProgram
import androidx.media3.effect.GlEffect
import androidx.media3.effect.GlShaderProgram

/**
 * The desktop app's `blur` layout: the whole stream picture fitted into a vertical frame, the rest filled
 * with the same picture enlarged, blurred and darkened. One pass on the GPU, no second decode.
 */
@UnstableApi
class BlurFitEffect(private val width: Int = 1080, private val height: Int = 1920) : GlEffect {
    override fun toGlShaderProgram(context: Context, useHdr: Boolean): GlShaderProgram = BlurFitProgram(width, height, useHdr)
}

@UnstableApi
private class BlurFitProgram(private val width: Int, private val height: Int, useHdr: Boolean) :
    BaseGlShaderProgram(/* useHighPrecisionColorComponents= */ useHdr, /* texturePoolCapacity= */ 1) {

    private val program: GlProgram = try {
        GlProgram(VERTEX, FRAGMENT).apply {
            setBufferAttribute("aFramePosition", GlUtil.getNormalizedCoordinateBounds(), GlUtil.HOMOGENEOUS_COORDINATE_VECTOR_SIZE)
        }
    } catch (e: GlUtil.GlException) {
        throw VideoFrameProcessingException(e)
    }

    override fun configure(inputWidth: Int, inputHeight: Int): Size {
        val input = inputWidth.toFloat() / inputHeight
        val output = width.toFloat() / height
        // Fit: the picture's share of the frame. Cover: the share of the picture the background shows.
        val fit = if (input > output) floatArrayOf(1f, output / input) else floatArrayOf(input / output, 1f)
        val cover = if (input > output) floatArrayOf(output / input, 1f) else floatArrayOf(1f, input / output)
        program.setFloatsUniform("uFit", fit)
        program.setFloatsUniform("uCover", cover)
        // Blur radius: a circle of BLUR_RADIUS of the output's height in output pixels, carried into the picture's
        // texture coordinates (the background shows `cover` of the picture in each direction).
        program.setFloatsUniform("uStep", floatArrayOf(BLUR_RADIUS * height / width * cover[0], BLUR_RADIUS * cover[1]))
        return Size(width, height)
    }

    override fun drawFrame(inputTexId: Int, presentationTimeUs: Long) {
        try {
            program.use()
            program.setSamplerTexIdUniform("uTexSampler", inputTexId, /* texUnitIndex= */ 0)
            program.bindAttributesAndUniforms()
            GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4)
            GlUtil.checkGlError()
        } catch (e: GlUtil.GlException) {
            throw VideoFrameProcessingException(e, presentationTimeUs)
        }
    }

    override fun release() {
        super.release()
        try {
            program.delete()
        } catch (e: GlUtil.GlException) {
            throw VideoFrameProcessingException(e)
        }
    }

    companion object {
        private const val VERTEX = """
            attribute vec4 aFramePosition;
            varying vec2 vCoord;
            void main() {
              gl_Position = aFramePosition;
              vCoord = aFramePosition.xy * 0.5 + 0.5;
            }
        """

        /** Blur radius as a share of the output's height: about the desktop's `gblur=sigma=24` on 1080x1920 (layouts.py). */
        private const val BLUR_RADIUS = 0.03f

        // 24 samples on a golden-angle spiral (a Vogel disk), weighted towards the centre, make the background blur:
        // a square grid of samples left ghost copies of the picture. Darkened by 0.06, as the desktop's `eq=brightness=-0.06`.
        private const val FRAGMENT = """
            precision mediump float;
            uniform sampler2D uTexSampler;
            uniform vec2 uFit;
            uniform vec2 uCover;
            uniform vec2 uStep;
            varying vec2 vCoord;
            void main() {
              vec2 inside = (vCoord - (vec2(1.0) - uFit) * 0.5) / uFit;
              if (inside.x >= 0.0 && inside.x <= 1.0 && inside.y >= 0.0 && inside.y <= 1.0) {
                gl_FragColor = texture2D(uTexSampler, inside);
              } else {
                vec2 centre = (vCoord - 0.5) * uCover + 0.5;
                vec3 sum = vec3(0.0);
                float total = 0.0;
                // The spiral turned by a different angle at each pixel (interleaved gradient noise): no swirl shows.
                float turn = 6.2831853 * fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
                for (int i = 0; i < 24; i++) {
                  float r = sqrt((float(i) + 0.5) / 24.0);
                  float a = float(i) * 2.39996 + turn;
                  float w = 1.0 - 0.6 * r;
                  sum += texture2D(uTexSampler, clamp(centre + vec2(cos(a), sin(a)) * r * uStep, 0.0, 1.0)).rgb * w;
                  total += w;
                }
                gl_FragColor = vec4(max(sum / total - 0.06, 0.0), 1.0);
              }
            }
        """
    }
}
