package com.quange.radioapk

import android.os.Bundle
import android.view.MenuItem
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.edit
import com.quange.radioapk.databinding.ActivitySettingsBinding

/** 设置页：改服务器地址 + 显示版本。改完保存到 SharedPreferences。 */
class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)
        supportActionBar?.setDisplayHomeAsUpEnabled(true)

        val prefs = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE)
        binding.editServerUrl.setText(
            prefs.getString(MainActivity.KEY_SERVER_URL, "http://localhost:8000")
        )

        binding.btnSave.setOnClickListener {
            val u = binding.editServerUrl.text.toString().trim().trimEnd('/')
            if (u.isEmpty()) {
                binding.editServerUrl.error = getString(R.string.err_empty_url)
                return@setOnClickListener
            }
            if (!(u.startsWith("http://") || u.startsWith("https://"))) {
                binding.editServerUrl.error = getString(R.string.err_invalid_url)
                return@setOnClickListener
            }
            prefs.edit { putString(MainActivity.KEY_SERVER_URL, u) }
            finish()
        }

        binding.btnReset.setOnClickListener {
            prefs.edit { remove(MainActivity.KEY_SERVER_URL) }
            finish()
        }

        binding.txtVersion.text = getString(R.string.version_fmt, BuildConfig.VERSION_NAME, BuildConfig.VERSION_CODE)
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        android.R.id.home -> { finish(); true }
        else -> super.onOptionsItemSelected(item)
    }
}
