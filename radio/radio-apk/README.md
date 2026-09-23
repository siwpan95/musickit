# 📻 Radio APK — 把 `radio/` 电台套壳成安卓应用

把 `radio/`（Flask 网络电台 + 网页控制面板）套壳成一个原生 Android APK。
**后端代码一行不改**，APK 只是个高级浏览器，加载控制面板网页。

---

## 📦 项目结构

```
radio-apk/
├── build.gradle.kts              # 顶层 Gradle 配置
├── settings.gradle.kts
├── gradle.properties
├── gradle/wrapper/
│   └── gradle-wrapper.properties # Gradle 8.10.2（首次同步自动下载）
└── app/
    ├── build.gradle.kts          # AGP 8.7.3 / Kotlin 2.0.20 / compileSdk 35 / minSdk 24
    ├── proguard-rules.pro
    └── src/main/
        ├── AndroidManifest.xml   # INTERNET 权限 + 明文 HTTP 允许
        ├── java/com/quange/radioapk/
        │   ├── MainActivity.kt   # WebView 套壳主界面
        │   └── SettingsActivity.kt # 改服务器地址
        └── res/
            ├── layout/            # activity_main / activity_settings
            ├── menu/main_menu.xml # 顶部菜单（刷新/直链/设置/切换服务器）
            ├── values/            # strings / colors / themes
            ├── xml/               # network_security_config（允许明文 HTTP）
            ├── drawable/          # 自适应图标前/背景（唱片+vaporwave 网格）
            ├── mipmap-anydpi-v26/ # 自适应图标（Android 8+）
            └── mipmap-*/          # 各密度 PNG（复用 radio 的 icon-192/512.png）
```

---

## 🚀 构建 APK

### 前置
- 已装 Android Studio 2026.1.2（在 `<Android Studio>\`）
- 首次打开会自动下载 Android SDK + Gradle 8.10.2（约 2~3 GB，挂代理或国内镜像更快）

### 步骤
1. 启动 Android Studio：
   ```
   <Android Studio>\bin\studio64.exe
   ```
2. **Open** → 选本目录（`<仓库根>/radio/radio-apk`）
3. 等 "Gradle Sync" 完成（首次会下载 SDK + Gradle + 依赖，10~30 分钟）
4. 顶部菜单 **Build → Build Bundle(s)/APK(s) → Build APK(s)**
5. 构建完成点通知栏 "locate" 链接，APK 在：
   ```
   app/build/outputs/apk/debug/app-debug.apk
   ```

### 命令行构建（可选，SDK 装好后）
```bash
cd radio/radio-apk                # 在仓库根执行，本目录即 radio-apk 工程
./gradlew assembleDebug
# 产物同上
```

### 签名发版
调试 APK 装手机够用。要正式签名上商店：
- **Build → Generate Signed Bundle / APK → APK → Create new keystore**
- 留好 keystore 密码（丢了就再也没法更新应用）

---

## 🎯 使用

1. 把 `app-debug.apk` 传到手机（QQ/微信/USB 都行）
2. 手机设置允许"未知来源应用安装"
3. 装好打开 → 弹出"服务器地址"输入框

### 服务器地址怎么填

| 场景 | 地址 | 备注 |
|------|------|------|
| 电脑本机调试（模拟器） | `http://10.0.2.2:8000` | 模拟器内 10.0.2.2 = 宿主机 |
| 手机连电脑（同 WiFi） | `http://电脑IP:8000` | 电脑 `ipconfig` 查 IPv4 |
| 公网收听 | `https://xxx.trycloudflare.com` | 电脑上 `python run.py --expose` |
| 公网收听（ngrok） | `https://xxx.ngrok-free.app` | `python run.py --expose ngrok` |

4. 进控制面板后所有功能（播放/切歌/转播/歌词/录音/扩展）跟网页完全一致
5. 顶部菜单：
   - 🔄 刷新
   - 🎵 直接收听 → 调起系统播放器放 `/stream`
   - 🔧 切换服务器 → 改地址
   - ⚙️ 设置 → 改地址 + 看版本

---

## 🛠️ 套壳都做了什么

- ✅ **明文 HTTP 流量**允许（控制面板默认 http://）
- ✅ **JS / DOM storage / 数据库** 全开（PWA 必需）
- ✅ **媒体自动播放**（音频流不卡手势）
- ✅ **Mixed content** 允许（穿透 https + 内嵌 http 资源）
- ✅ **跟随系统暗色主题**（webkit Algorithmic Darkening）
- ✅ **返回键**先退 WebView 历史
- ✅ **JS alert/confirm** 用系统对话框代理
- ✅ **麦克风权限**：网页请求录音时自动转 Android 运行时权限
- ✅ **服务器地址**存 SharedPreferences，卸载重装备份恢复
- ✅ **图标**复用 radio 的 PWA 图标
- ✅ **零耦合**：不 import 任何 radio 后端代码，后端怎么演进都不影响套壳

---

## ⚠️ 限制

- 后端服务必须自己跑（电脑/服务器/树莓派），APK 不包含后端
- 后台播放：锁屏后音频流可能被系统省电策略中断，需要在手机设置里给本应用"不限制后台"
- 转播 AAC/OGG 流需要后端有 ffmpeg，跟套壳无关
- 没做 ExoPlayer 原生播放器集成，音频流走 WebView（控制面板已经处理得很好）
