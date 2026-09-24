pragma Singleton

// All user-facing copy of Svoya Shell, Russian and English (DESIGN.md §8:
// short, calm, concrete; lowercase in the bar, sentence case elsewhere; never nag).
//
// Language: Settings.language ("ru"/"en") if set, otherwise $LANGUAGE, $LC_ALL,
// $LC_MESSAGES, $LANG. The greeter can switch it at runtime via `override`.

import QtQuick
import Quickshell

Singleton {
    id: root

    property string override: ""

    readonly property string systemLang: {
        const vars = ["LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"];
        for (let i = 0; i < vars.length; i++) {
            const v = Quickshell.env(vars[i]);
            if (v && v.length > 0 && v !== "C" && v !== "POSIX")
                return v.toLowerCase().indexOf("ru") === 0 ? "ru" : "en";
        }
        return "en";
    }
    readonly property string lang: root.override.length > 0 ? root.override : (Settings.language.length > 0 ? Settings.language : root.systemLang)
    readonly property bool ru: root.lang === "ru"
    readonly property string locale: root.ru ? "ru_RU" : "en_US"

    function t(ruText, enText) {
        return root.ru ? ruText : enText;
    }

    // Russian plural forms: 1 токен, 2 токена, 5 токенов.
    function plural(n, one, few, many) {
        const a = Math.abs(Math.floor(n)) % 100;
        const b = a % 10;
        if (a > 10 && a < 20)
            return many;
        if (b > 1 && b < 5)
            return few;
        if (b === 1)
            return one;
        return many;
    }

    function count(n, ruOne, ruFew, ruMany, enOne, enMany) {
        const num = Fmt.integer(n);
        if (root.ru)
            return num + " " + root.plural(n, ruOne, ruFew, ruMany);
        return num + " " + (Math.abs(n) === 1 ? enOne : enMany);
    }

    function tokens(n) { return root.count(n, "токен", "токена", "токенов", "token", "tokens"); }
    function requests(n) { return root.count(n, "запрос", "запроса", "запросов", "request", "requests"); }
    function devices(n) { return root.count(n, "устройство", "устройства", "устройств", "device", "devices"); }
    function cores(n) { return root.count(n, "ядро", "ядра", "ядер", "core", "cores"); }
    function modules(n) { return root.count(n, "модуль", "модуля", "модулей", "module", "modules"); }
    function minutesAgo(n) { return root.ru ? n + " мин назад" : n + " min ago"; }
    function hoursAgo(n) { return root.ru ? n + " ч назад" : n + " h ago"; }

    // ---- calendar (bar clock: «Чт 24 сен») ----------------------------------------
    readonly property var daysShort: root.ru ? ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"] : ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    readonly property var daysLong: root.ru ? ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"] : ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    readonly property var monthsShort: root.ru ? ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"] : ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    readonly property var monthsLong: root.ru ? ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"] : ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

    function barDate(d) {
        return root.daysShort[d.getDay()] + " " + d.getDate() + " " + root.monthsShort[d.getMonth()];
    }

    function longDate(d) {
        if (root.ru)
            return root.daysLong[d.getDay()] + ", " + d.getDate() + " " + root.monthsLong[d.getMonth()];
        return root.daysLong[d.getDay()] + ", " + root.monthsLong[d.getMonth()] + " " + d.getDate();
    }

    // ---- brand -------------------------------------------------------------------
    readonly property string osName: "Svoya OS"
    readonly property string osNameLocal: root.t("СОС — Своя Операционная Система", "Svoya OS — your own operating system")
    readonly property string codename: root.t("первый сигнал", "first signal")
    readonly property string morse: "··· ——— ···"

    // ---- bar -------------------------------------------------------------------------
    readonly property string gpu: "GPU"
    readonly property string gb: root.t("ГБ", "GB")
    readonly property string sosMenu: root.t("Меню СОС", "SOS menu")
    readonly property string workspace: root.t("Рабочий стол", "Workspace")
    readonly property string keyboardLayout: root.t("Раскладка", "Keyboard layout")

    // ---- СОС menu ------------------------------------------------------------------------
    readonly property string about: root.t("О системе", "About")
    readonly property string settings: root.t("Настройки", "Settings")
    readonly property string modulesTitle: root.t("Модули", "Modules")
    readonly property string doctor: root.t("Доктор", "Doctor")
    readonly property string session: root.t("Сеанс", "Session")

    // ---- Jackson -------------------------------------------------------------------------
    readonly property string jackson: root.t("Джексон", "Jackson")
    readonly property string jacksonPlaceholder: root.t("Спроси что-нибудь…", "Ask anything…")
    readonly property string jacksonRefinePlaceholder: root.t("Уточни запрос…", "Refine the request…")
    readonly property string jacksonShotPlaceholder: root.t("Что сделать со снимком?", "What should I do with the screenshot?")
    readonly property string jacksonOffline: root.t("не в сети", "offline")
    readonly property string jacksonOfflineBody: root.t("Джексон сейчас не отвечает. Он запускается вместе с сеансом; проверить можно в «Доктор».", "Jackson is not answering right now. It starts with the session; the Doctor can check it.")
    readonly property string jacksonDisabled: root.t("ИИ выключен", "AI is off")
    readonly property string jacksonConnecting: root.t("подключение…", "connecting…")
    readonly property string jacksonListening: root.t("слушаю…", "listening…")
    readonly property string jacksonThinking: root.t("думаю…", "thinking…")
    readonly property string local: root.t("локально", "local")
    readonly property string cloud: root.t("облако", "cloud")
    readonly property string refine: root.t("уточнить", "refine")
    readonly property string close: root.t("закрыть", "close")
    readonly property string stop: root.t("остановить", "stop")
    readonly property string send: root.t("отправить", "send")
    readonly property string retry: root.t("Повторить", "Retry")
    readonly property string undo: root.t("Отменить", "Undo")
    readonly property string screenshotAttached: root.t("снимок экрана", "screenshot")
    readonly property string dataStayed: root.t("данные не покидали компьютер", "data stayed on this computer")
    function dataLeft(provider) {
        return root.ru ? "запрос ушёл в облако" + (provider ? " · " + provider : "") : "sent to the cloud" + (provider ? " · " + provider : "");
    }
    function seconds(ms) {
        return Fmt.num(ms / 1000, 1) + (root.ru ? " с" : " s");
    }
    function euro(v) {
        return Fmt.money(v) + " €";
    }
    readonly property string approvalTitle: root.t("Нужно твоё разрешение", "Needs your permission")
    readonly property string approveOnce: root.t("Разрешить один раз", "Allow once")
    readonly property string approveAlways: root.t("Всегда в этом проекте", "Always in this project")
    readonly property string deny: root.t("Отклонить", "Deny")
    readonly property string approved: root.t("разрешено", "allowed")
    readonly property string denied: root.t("отклонено", "denied")
    readonly property var tierNames: root.ru ? ["только чтение", "обратимое изменение", "действие вовне", "изменение системы", "секреты"] : ["read-only", "reversible change", "external action", "system change", "secrets"]
    readonly property string toolRunning: root.t("выполняется", "running")
    readonly property string toolDone: root.t("готово", "done")
    readonly property string toolFailed: root.t("не удалось", "failed")
    readonly property string turnCancelled: root.t("Остановлено.", "Stopped.")
    readonly property string fits: root.t("влезет", "fits")

    // ---- launcher --------------------------------------------------------------------------
    readonly property string launcherPlaceholder: root.t("Найти приложение, файл, настройку… (? — спросить Джексона)", "Find an app, file, setting… (? — ask Jackson)")
    readonly property string groupApps: root.t("Приложения", "Apps")
    readonly property string groupFiles: root.t("Файлы", "Files")
    readonly property string groupSettings: root.t("Настройки", "Settings")
    readonly property string groupModules: root.t("Модули", "Modules")
    readonly property string groupActions: root.t("Действия", "Actions")
    readonly property string groupJackson: root.t("Джексон", "Jackson")
    readonly property string askJackson: root.t("Спросить Джексона", "Ask Jackson")
    readonly property string nothingFound: root.t("Ничего не нашлось", "Nothing found")
    readonly property string open: root.t("открыть", "open")
    readonly property string run: root.t("запустить", "run")
    readonly property string install: root.t("установить", "install")
    readonly property string installed: root.t("установлен", "installed")

    // settings entries (launcher group «Настройки»)
    readonly property string wifi: "Wi-Fi"
    readonly property string bluetooth: "Bluetooth"
    readonly property string sound: root.t("Звук", "Sound")
    readonly property string brightness: root.t("Яркость", "Brightness")
    readonly property string theme: root.t("Тема", "Theme")
    readonly property string focus: root.t("Фокус", "Focus")
    readonly property string focusMode: root.t("Режим фокуса", "Focus mode")
    readonly property string accessibility: root.t("Специальные возможности", "Accessibility")
    readonly property string setupWizard: root.t("Первоначальная настройка", "Setup wizard")
    readonly property string shortcuts: root.t("Горячие клавиши", "Keyboard shortcuts")
    readonly property string aiPrivacy: root.t("ИИ и приватность", "AI & privacy")
    readonly property string layoutPreset: root.t("Раскладка окон", "Window layout")
    readonly property string notifications: root.t("Уведомления", "Notifications")

    // ---- actions ---------------------------------------------------------------------------------
    readonly property string lock: root.t("Заблокировать", "Lock")
    readonly property string logout: root.t("Выйти из сеанса", "Log out")
    readonly property string suspend: root.t("Сон", "Suspend")
    readonly property string reboot: root.t("Перезагрузить", "Restart")
    readonly property string poweroff: root.t("Выключить", "Shut down")
    readonly property string screenshotRegion: root.t("Снимок области", "Region screenshot")
    readonly property string clipboard: root.t("Буфер обмена", "Clipboard")
    readonly property string undoSystem: root.t("Отменить последнее изменение системы", "Undo last system change")
    readonly property string toggleTiling: root.t("Плитка на этом столе", "Tiling on this workspace")
    readonly property string dnd: root.t("Не беспокоить", "Do not disturb")
    readonly property string terminal: root.t("Терминал", "Terminal")
    readonly property string files: root.t("Файлы", "Files")
    readonly property string confirmAgain: root.t("Нажми ещё раз, чтобы подтвердить", "Press again to confirm")
    readonly property string cancel: root.t("Отмена", "Cancel")

    // ---- control center -------------------------------------------------------------------------
    readonly property string network: root.t("Сеть", "Network")
    readonly property string connected: root.t("подключено", "connected")
    readonly property string connecting: root.t("подключение…", "connecting…")
    readonly property string connect: root.t("Подключить", "Connect")
    readonly property string disconnect: root.t("Отключить", "Disconnect")
    readonly property string password: root.t("Пароль", "Password")
    readonly property string wifiOff: root.t("Wi-Fi выключен", "Wi-Fi is off")
    readonly property string noNetworks: root.t("Сети не найдены", "No networks found")
    readonly property string wired: root.t("проводная сеть", "wired")
    readonly property string offline: root.t("нет сети", "offline")
    readonly property string btOff: root.t("выключен", "off")
    readonly property string btOn: root.t("включён", "on")
    readonly property string unavailable: root.t("недоступно", "unavailable")
    readonly property string muted: root.t("без звука", "muted")
    readonly property string graphite: root.t("Графит", "Graphite")
    readonly property string paper: root.t("Бумага", "Paper")
    readonly property string phosphor: root.t("Фосфор", "Phosphor")
    readonly property string auto: root.t("Авто", "Auto")
    readonly property string focusWork: root.t("Работа", "Work")
    readonly property string focusStudy: root.t("Обучение", "Study")
    readonly property string focusPresentation: root.t("Презентация", "Presentation")
    readonly property string route: root.t("Маршрут", "Route")
    readonly property string spentToday: root.t("Сегодня потрачено", "Spent today")
    readonly property string leftToday: root.t("Покинули компьютер сегодня", "Left this computer today")
    readonly property string aiLocalOnly: root.t("всё локально", "everything local")
    readonly property string clearAll: root.t("Очистить", "Clear")
    readonly property string noNotifications: root.t("Уведомлений нет", "No notifications")
    readonly property string now: root.t("сейчас", "now")
    readonly property string volume: root.t("Громкость", "Volume")

    // ---- clipboard ------------------------------------------------------------------------------
    readonly property string clipboardPlaceholder: root.t("Поиск в истории буфера…", "Search clipboard history…")
    readonly property string clipboardEmpty: root.t("История пуста", "History is empty")
    readonly property string clipboardMissing: root.t("История буфера появится, когда будет установлен cliphist", "Clipboard history needs cliphist")
    readonly property string image: root.t("Изображение", "Image")
    readonly property string copied: root.t("Скопировано", "Copied")
    readonly property string deleteKey: root.t("удалить", "delete")
    readonly property string copy: root.t("Копировать", "Copy")

    // ---- screenshot -------------------------------------------------------------------------------
    readonly property string screenshot: root.t("Снимок", "Screenshot")
    readonly property string extractText: root.t("Распознать текст", "Extract text")
    readonly property string save: root.t("Сохранить", "Save")
    readonly property string textCopied: root.t("Текст скопирован", "Text copied")
    readonly property string ocrMissing: root.t("Распознавание текста появится с модулем OCR", "Text recognition arrives with the OCR module")
    readonly property string screenshotTools: root.t("Для снимков нужны grim и slurp", "Screenshots need grim and slurp")
    function savedTo(p) {
        return root.t("Сохранено: ", "Saved: ") + p;
    }

    // ---- cheat sheet ---------------------------------------------------------------------------------
    readonly property string csLauncher: root.t("Поиск и команды", "Search and commands")
    readonly property string csJackson: root.t("Джексон; удерживать — говорить", "Jackson; hold to talk")
    readonly property string csClipboard: root.t("История буфера обмена", "Clipboard history")
    readonly property string csShot: root.t("Снимок области", "Region screenshot")
    readonly property string csTerminal: root.t("Терминал", "Terminal")
    readonly property string csFiles: root.t("Файлы", "Files")
    readonly property string csClose: root.t("Закрыть окно", "Close window")
    readonly property string csFullscreen: root.t("Во весь экран", "Fullscreen")
    readonly property string csTiling: root.t("Плитка на этом столе", "Tiling on this workspace")
    readonly property string csWorkspaces: root.t("Рабочие столы", "Workspaces")
    readonly property string csMoveToWorkspace: root.t("Перенести окно на стол", "Move window to workspace")
    readonly property string csCheatsheet: root.t("Эта шпаргалка", "This cheat sheet")
    readonly property string csUndo: root.t("Отменить изменение системы", "Undo system change")
    readonly property string csDoctor: root.t("Доктор системы", "System Doctor")
    readonly property string csLock: root.t("Заблокировать", "Lock")
    readonly property string csControlCenter: root.t("Центр управления", "Control center")
    readonly property string csSession: root.t("Сеанс: выйти, сон, выключить", "Session: log out, suspend, shut down")
    readonly property string csAccessibility: root.t("Специальные возможности", "Accessibility")
    readonly property string csLayout: root.t("Сменить раскладку", "Switch keyboard layout")
    readonly property string csFocus: root.t("Фокус между окнами", "Move focus")

    // ---- about -------------------------------------------------------------------------------------------
    readonly property string version: root.t("Версия", "Version")
    readonly property string licenses: root.t("Код — Apache-2.0 · иконки — Lucide (ISC) · шрифты — IBM Plex (OFL), Departure Mono (MIT)", "Code — Apache-2.0 · icons — Lucide (ISC) · fonts — IBM Plex (OFL), Departure Mono (MIT)")
    readonly property string promise: root.t("Без рекламы, аккаунтов и телеметрии. ИИ не запускается сам.", "No ads, no accounts, no telemetry. AI never starts by itself.")

    // ---- lock / greeter ------------------------------------------------------------------------------------
    readonly property string passwordPlaceholder: root.t("Пароль", "Password")
    readonly property string wrongPassword: root.t("Пароль не подошёл", "That password didn't work")
    readonly property string checking: root.t("Проверяю…", "Checking…")
    readonly property string lockUnavailable: root.t("Блокировка недоступна: нет файла PAM", "Lock is unavailable: PAM file missing")
    readonly property string user: root.t("Пользователь", "User")
    readonly property string language: root.t("Язык", "Language")
    readonly property string login: root.t("Войти", "Log in")
    readonly property string loggingIn: root.t("Вход…", "Logging in…")
    readonly property string greeterError: root.t("Не удалось начать сеанс", "Could not start the session")

    // ---- POST splash -----------------------------------------------------------------------------------------
    readonly property string postCpu: root.t("ЦП  ", "CPU ")
    readonly property string postGpu: root.t("ГП  ", "GPU ")
    readonly property string postRam: root.t("ОЗУ ", "RAM ")
    readonly property string postJackson: root.t("ДЖЕКСОН", "JACKSON")
    readonly property string driver: root.t("драйвер", "driver")
    readonly property string disk: root.t("диск", "disk")
    readonly property string free: root.t("свободно", "free")
    readonly property string ready: root.t("готов", "ready")
    readonly property string notRunning: root.t("не запущен", "not running")
    readonly property string noGpu: root.t("встроенная графика", "integrated graphics")

    // ---- OSD ---------------------------------------------------------------------------------------------
    readonly property string osdVolume: root.t("громкость", "volume")
    readonly property string osdBrightness: root.t("яркость", "brightness")
    readonly property string osdMuted: root.t("без звука", "muted")

    // ---- notifications ------------------------------------------------------------------------------------
    readonly property string undoDone: root.t("Последнее изменение отменено", "The last change was undone")
    readonly property string undoFailed: root.t("Отменить не получилось", "Undo did not work")
    readonly property string tilingOn: root.t("Плитка включена", "Tiling on")
    readonly property string tilingOff: root.t("Плавающие окна", "Floating windows")
    readonly property string jacksonDone: root.t("Джексон ответил", "Jackson answered")

    // ---- first-run wizard ---------------------------------------------------------------------------------
    readonly property string wizNext: root.t("Далее", "Next")
    readonly property string wizBack: root.t("Назад", "Back")
    readonly property string wizSkip: root.t("Пропустить", "Skip")
    readonly property string wizDone: root.t("Готово", "Done")
    readonly property string wizWelcome: root.t("Добро пожаловать в Свою", "Welcome to Svoya")
    readonly property string wizStepOf: root.t("шаг", "step")
    readonly property string wizReversible: root.t("Каждый выбор можно изменить позже.", "Every choice can be changed later.")
    readonly property string wizA11yTitle: root.t("Специальные возможности", "Accessibility")
    readonly property string wizA11yBody: root.t("Этот шаг всегда доступен по Super + Alt + A.", "This step is always one press away: Super + Alt + A.")
    readonly property string wizReduceMotion: root.t("Меньше движения", "Reduce motion")
    readonly property string wizReduceMotionHint: root.t("Панели появляются без анимации, осциллограф неподвижен.", "Panels appear without animation; the scope stays still.")
    readonly property string wizHighContrast: root.t("Высокий контраст", "High contrast")
    readonly property string wizHighContrastHint: root.t("Тусклый текст и линии становятся ярче.", "Dim text and hairlines get stronger.")
    readonly property string wizLargeText: root.t("Крупнее текст в панелях", "Larger text in panels")
    readonly property string wizLargeTextHint: root.t("Текст панелей и мастера на 15 % крупнее.", "Panel and wizard text 15% larger.")
    readonly property string wizStartupSound: root.t("Звук при входе", "Startup sound")
    readonly property string wizStartupSoundHint: root.t("Короткое «··· ——— ···» синусом.", "A short sine «··· ——— ···».")
    readonly property string wizLangTitle: root.t("Язык и клавиатура", "Language and keyboard")
    readonly property string wizLangBody: root.t("Язык интерфейса и раскладки клавиатуры.", "Interface language and keyboard layouts.")
    readonly property string wizUiLanguage: root.t("Язык интерфейса", "Interface language")
    readonly property string wizLayouts: root.t("Раскладки", "Layouts")
    readonly property string wizSwitchKey: root.t("Переключение", "Switch with")
    readonly property string wizLookTitle: root.t("Внешний вид", "Look")
    readonly property string wizLookBody: root.t("Графит ночью, Бумага днём. Авто переключает их по закату и рассвету.", "Graphite by night, Paper by day. Auto follows sunset and sunrise.")
    readonly property string wizLayoutTitle: root.t("Окна", "Windows")
    readonly property string wizLayoutBody: root.t("Как располагаются окна. Переключить можно в любой момент.", "How windows are arranged. Switch any time.")
    readonly property string wizClean: root.t("Чистый", "Clean")
    readonly property string wizCleanHint: root.t("Плавающие окна, как привычно. Super + T включает плитку для стола.", "Floating windows, as you're used to. Super + T tiles a workspace.")
    readonly property string wizClassic: root.t("Классический", "Classic")
    readonly property string wizClassicHint: root.t("Панель задач снизу, плавающие окна.", "Taskbar at the bottom, floating windows.")
    readonly property string wizHacker: root.t("Хакер", "Hacker")
    readonly property string wizHackerHint: root.t("Плитка везде, без заголовков, акцентная рамка.", "Tiling everywhere, no title bars, accent border.")
    readonly property string wizProfileTitle: root.t("Для чего этот компьютер", "What this computer is for")
    readonly property string wizProfileBody: root.t("Профиль выбирает модули. Ничего не ставится без твоего «Далее».", "A profile picks modules. Nothing installs until you press Next.")
    readonly property string profNewcomer: root.t("Новичок", "Newcomer")
    readonly property string profNewcomerHint: root.t("Браузер, документы, Джексон локально.", "Browser, documents, local Jackson.")
    readonly property string profCreator: root.t("Автор", "Creator")
    readonly property string profCreatorHint: root.t("Картинки, видео и голос на своей видеокарте.", "Images, video and voice on your own GPU.")
    readonly property string profMl: root.t("ML-инженер", "ML engineer")
    readonly property string profMlHint: root.t("Лаборатория, CUDA по проектам, трекинг экспериментов.", "ML lab, per-project CUDA, experiment tracking.")
    readonly property string profAgent: root.t("Агенты", "Agent builder")
    readonly property string profAgentHint: root.t("Песочницы, MCP, кодовые агенты.", "Sandboxes, MCP, coding agents.")
    readonly property string profHacker: root.t("Хакер", "Hacker")
    readonly property string profHackerHint: root.t("Минимум по умолчанию, всё под рукой.", "Minimal defaults, everything at hand.")
    readonly property string profOffline: root.t("Только офлайн", "Offline only")
    readonly property string profOfflineHint: root.t("Без облачных модулей и облачного маршрута.", "No cloud modules and no cloud route.")
    readonly property string wizModulesToInstall: root.t("Будет установлено", "Will be installed")
    readonly property string wizInstalling: root.t("Устанавливаю в фоне", "Installing in the background")
    readonly property string wizCatalogMissing: root.t("Каталог модулей не найден. Модули можно добавить позже: svoya modules add.", "Module catalog not found. Add modules later: svoya modules add.")
    readonly property string wizAiTitle: root.t("Джексон и модели", "Jackson and models")
    readonly property string wizAiBody: root.t("Локально по умолчанию. Облако — только если ты добавишь ключ.", "Local by default. Cloud only if you add a key.")
    readonly property string wizGpuDetected: root.t("Видеокарта", "Graphics card")
    readonly property string wizSuggestedModel: root.t("Подходящая локальная модель", "Suggested local model")
    readonly property string wizCloudKeys: root.t("Ключи облачных моделей (необязательно)", "Cloud model keys (optional)")
    readonly property string wizKeyStored: root.t("сохранён в связке ключей", "stored in the keyring")
    readonly property string wizKeyFailed: root.t("не удалось сохранить", "could not store")
    readonly property string wizPrivacyTitle: root.t("Приватность", "Privacy")
    readonly property string wizPrivacyBody: root.t("Что остаётся на компьютере и как всё вернуть.", "What stays on this computer and how to undo anything.")
    readonly property string wizPrivacy1: root.t("Без рекламы, аккаунта и телеметрии.", "No ads, no account, no telemetry.")
    readonly property string wizPrivacy2: root.t("ИИ не запускается сам; всё отключается одним переключателем.", "AI never starts by itself; one switch turns it off.")
    readonly property string wizPrivacy3: root.t("Каждый запрос в облако виден в панели и в центре управления.", "Every cloud request is visible in the panel and the control center.")
    readonly property string wizPrivacy4: root.t("Любое изменение отменяется: Super + Z.", "Any change can be undone: Super + Z.")
    readonly property string wizSnapshot: root.t("Сделать первый снимок системы", "Take the first system snapshot")
    readonly property string wizSnapshotDone: root.t("Снимок сохранён", "Snapshot saved")
    readonly property string wizSnapshotFailed: root.t("Снимок не получился; повторить можно позже", "Snapshot failed; you can retry later")
    readonly property string wizShortcuts: root.t("Главные клавиши", "Key shortcuts")
    readonly property string wizFinish: root.t("Начать работу", "Start")
}
