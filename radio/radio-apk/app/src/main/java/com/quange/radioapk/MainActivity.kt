package com.quange.radioapk

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.edit
import androidx.core.view.isVisible
import androidx.webkit.WebViewFeature
import androidx.webkit.WebSettingsCompat
import com.quange.radioapk.databinding.ActivityMainBinding

/**
 * 套壳主界面：把 Flask 控制面板塞进 WebView。
 *
 * 设计：
 * - 后端一行不改，套壳只是个浏览器。
 * - 服务器地址存 SharedPreferences（key=server_url），首次启动为空 → 弹输入框。
 * - 允许明文 HTTP（控制面板默认 http://），启用 DOM storage / 后台媒体 / JS。
 * - 返回键先退 WebView 历史，再退 Activity。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var pendingPermissionRequest: PermissionRequest? = null

    private val serverUrl: String
        get() = getSharedPreferences(PREFS, MODE_PRIVATE)
            .getString(KEY_SERVER_URL, "").orEmpty().trim()

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)
        supportActionBar?.title = getString(R.string.app_name)

        setupWebView()
        setupBackHandler()

        if (savedInstanceState != null) {
            binding.webView.restoreState(savedInstanceState)
        } else if (serverUrl.isEmpty()) {
            askForServerUrl(firstRun = true)
        } else {
            loadHome()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        with(binding.webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true            // PWA / localStorage 必需
            databaseEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            mediaPlaybackRequiresUserGesture = false   // 音频流自动播
            cacheMode = android.webkit.WebSettings.LOAD_DEFAULT
            // mixed content（同页 http(s) 资源）允许，控制面板混合资源常见
            mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            // UA 加标记，方便后端识别（可选）
            userAgentString = (userAgentString ?: "") + " RadioApk/1.0"
            // 自适应屏幕
            useWideViewPort = true
            loadWithOverviewMode = true
            setSupportZoom(true)
            builtInZoomControls = true
            displayZoomControls = false
        }

        // 跟随系统暗色主题
        if (WebViewFeature.isFeatureSupported(WebViewFeature.ALGORITHMIC_DARKENING)) {
            WebSettingsCompat.setAlgorithmicDarkeningAllowed(binding.webView.settings, true)
        }

        binding.webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest): Boolean {
                // 控制面板内的链接若跳出本服务器，交给系统浏览器
                val host = req.url.host
                val srvHost = Uri.parse(serverUrl).host
                return if (host != null && host != srvHost) {
                    startActivity(Intent(Intent.ACTION_VIEW, req.url))
                    true
                } else false
            }

            override fun onReceivedError(
                view: WebView?, req: WebResourceRequest?, err: android.webkit.WebResourceError?
            ) {
                super.onReceivedError(view, req, err)
                if (req?.isForMainFrame == true) showError(err?.description?.toString().orEmpty())
            }
        }

        binding.webView.webChromeClient = object : WebChromeClient() {
            // JS alert/prompt/confirm 用系统对话框代理
            override fun onJsAlert(view: WebView, url: String, message: String, r: android.webkit.JsResult): Boolean {
                AlertDialog.Builder(this@MainActivity).setMessage(message)
                    .setPositiveButton(android.R.string.ok) { _, _ -> r.confirm() }
                    .setOnCancelListener { r.cancel() }
                    .show()
                return true
            }

            override fun onJsConfirm(view: WebView, url: String, message: String, r: android.webkit.JsResult): Boolean {
                AlertDialog.Builder(this@MainActivity).setMessage(message)
                    .setPositiveButton(android.R.string.ok) { _, _ -> r.confirm() }
                    .setNegativeButton(android.R.string.cancel) { _, _ -> r.cancel() }
                    .setOnCancelListener { r.cancel() }
                    .show()
                return true
            }

            // 处理网页麦克风/录音权限请求 → 转成 Android 运行时权限
            override fun onPermissionRequest(request: PermissionRequest) {
                if (PermissionRequest.RESOURCE_AUDIO_CAPTURE in request.resources) {
                    pendingPermissionRequest = request
                    micPermissionLauncher.launch(android.Manifest.permission.RECORD_AUDIO)
                } else {
                    request.deny()
                }
            }
        }

        binding.swipeRefresh.setOnRefreshListener { binding.webView.reload() }
    }

    private val micPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        // 主回调：grant/deny WebView pending 请求
        pendingPermissionRequest?.let { req ->
            if (granted) req.grant(req.resources) else req.deny()
            pendingPermissionRequest = null
        }
    }

    private fun setupBackHandler() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.webView.canGoBack()) binding.webView.goBack()
                else { isEnabled = false; finish() }
            }
        })
    }

    private fun loadHome() {
        val url = serverUrl.ifEmpty { return }
        binding.errorView.isVisible = false
        binding.webView.loadUrl(url)
        supportActionBar?.subtitle = url.removePrefix("http://").removePrefix("https://")
    }

    private fun askForServerUrl(firstRun: Boolean) {
        val edit = EditText(this).apply {
            hint = "http://192.168.1.100:8000"
            inputType = android.text.InputType.TYPE_TEXT_VARIATION_URI
            setText(if (firstRun) "http://localhost:8000" else serverUrl)
            setSelection(text.length)
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.dialog_server_title)
            .setMessage(R.string.dialog_server_msg)
            .setView(edit)
            .setPositiveButton(android.R.string.ok) { _, _ ->
                val u = edit.text.toString().trim().trimEnd('/')
                if (u.isNotEmpty()) {
                    getSharedPreferences(PREFS, MODE_PRIVATE).edit { putString(KEY_SERVER_URL, u) }
                    loadHome()
                } else if (firstRun) finish()
            }
            .setNegativeButton(android.R.string.cancel) { _, _ -> if (firstRun) finish() }
            .setCancelable(!firstRun)
            .show()
    }

    private fun showError(msg: String) {
        binding.errorView.text = getString(R.string.err_load, msg, serverUrl)
        binding.errorView.isVisible = true
        binding.swipeRefresh.isRefreshing = false
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean = when (item.itemId) {
        R.id.action_refresh -> { binding.webView.reload(); true }
        R.id.action_stream  -> {
            val u = serverUrl.trimEnd('/') + "/stream"
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(u)))
            true
        }
        R.id.action_settings -> {
            startActivity(Intent(this, SettingsActivity::class.java))
            true
        }
        R.id.action_change_server -> { askForServerUrl(firstRun = false); true }
        else -> super.onOptionsItemSelected(item)
    }

    override fun onResume() {
        super.onResume()
        binding.webView.onResume()
    }

    override fun onPause() {
        binding.webView.onPause()
        super.onPause()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        binding.webView.saveState(outState)
    }

    override fun onDestroy() {
        binding.webView.apply {
            stopLoading()
            removeAllViews()
            destroy()
        }
        super.onDestroy()
    }

    /** 从设置页回来后如果地址变了就重新加载。 */
    override fun onRestart() {
        super.onRestart()
        val current = binding.webView.url
        val srv = serverUrl
        if (srv.isNotEmpty() && current != null && !current.startsWith(srv)) loadHome()
    }

    companion object {
        const val PREFS = "radio_apk_prefs"
        const val KEY_SERVER_URL = "server_url"
    }
}
