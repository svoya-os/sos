pragma Singleton

// All user-facing copy of the SOS Shell, Russian and English (DESIGN.md §8:
// short, calm, concrete; lowercase in the bar, sentence case elsewhere; never nag).
//
// Language: Settings.language ("ru"/"en") if set, otherwise $LANGUAGE, $LC_ALL,
// $LC_MESSAGES, $LANG. The greeter can switch it at runtime via `langOverride`.

import QtQuick
import Quickshell

Singleton {
    id: root

    // (not `override`: that becomes a QML keyword after Qt 6.10)
    property string langOverride: ""

    readonly property string systemLang: {
        const vars = ["LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"];
        for (let i = 0; i < vars.length; i++) {
            const v = Quickshell.env(vars[i]);
            if (v && v.length > 0 && v !== "C" && v !== "POSIX")
                return v.toLowerCase().indexOf("ru") === 0 ? "ru" : "en";
        }
        return "en";
    }
    readonly property string lang: root.langOverride.length > 0 ? root.langOverride : (Settings.language.length > 0 ? Settings.language : root.systemLang)
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
    readonly property string osName: "SOS"
    readonly property string osNameLocal: root.t("СОС — Своя Операционная Система", "SOS — Svoya Operating System")
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
    readonly property string whileAway: root.t("пока тебя нет:", "while you're away:")
    readonly property string a11yShort: root.t("спец. возможности", "accessibility")
    readonly property string otherUser: root.t("другой пользователь", "other user")
    readonly property string sessionLabel: root.t("Сессия", "Session")
    readonly property string userNamePlaceholder: root.t("Имя пользователя", "User name")
    readonly property string enterUserName: root.t("Введи имя пользователя", "Type a user name")
    function left(sec) {
        return root.ru ? "ещё " + Fmt.duration(sec) : Fmt.duration(sec) + " left";
    }
    // "четверг · 24 сентября" (lock screen, greeter)
    function lockDate(d) {
        if (root.ru)
            return root.daysLong[d.getDay()] + " · " + d.getDate() + " " + root.monthsLong[d.getMonth()];
        return root.daysLong[d.getDay()] + " · " + root.monthsLong[d.getMonth()] + " " + d.getDate();
    }
    // "вход вчера в 23:40" (greeter user tiles)
    function lastLogin(d, now) {
        if (!d || isNaN(d.getTime()))
            return "";
        const day = 86400000;
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
        const at = Fmt.clock(d);
        if (d.getTime() >= start)
            return root.t("вход сегодня в " + at, "last login today at " + at);
        if (d.getTime() >= start - day)
            return root.t("вход вчера в " + at, "last login yesterday at " + at);
        return root.t("вход " + d.getDate() + " " + root.monthsLong[d.getMonth()], "last login " + root.monthsLong[d.getMonth()] + " " + d.getDate());
    }

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
    readonly property string wizWelcome: root.t("Добро пожаловать в СОС", "Welcome to SOS")
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
    readonly property string wizCatalogMissing: root.t("Профили недоступны. Модули можно добавить позже: sos install <модуль>.", "Profiles are unavailable. Add modules later: sos install <module>.")
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

    // wizard frame and steps (design/mockups/setup-*.html)
    readonly property string wzBrand: root.t("Настройка", "Setup")
    readonly property string wzFirstRun: root.t("· первый запуск", "· first run")
    readonly property string wzA11yOnly: root.t("· специальные возможности", "· accessibility")
    readonly property string wzSkipAll: root.t("пропустить настройку", "skip setup")
    readonly property string wzNext: root.t("Дальше", "Next")
    readonly property string wzBack: root.t("Назад", "Back")
    readonly property string wzClose: root.t("Закрыть", "Close")
    readonly property string wzFootNote: root.t("каждый шаг можно пропустить · любой выбор <b>отменяется</b>", "every step can be skipped · every choice <b>can be undone</b>")
    readonly property var wzEyebrows: root.ru ? ["Доступность", "Язык", "Оформление", "Окна", "Профиль", "ИИ", "Готово"] : ["Accessibility", "Language", "Appearance", "Windows", "Profile", "AI", "Done"]
    readonly property var wzTitles: root.ru ? ["Удобно ли смотреть и читать?", "На каком языке говорим?", "Как будет выглядеть система?", "Как расставлять окна?", "Чем ты будешь заниматься?", "Джексон и модели", "Что остаётся у тебя"] : ["Is everything easy to see and read?", "Which language do we speak?", "How should the system look?", "How should windows be arranged?", "What will you do with it?", "Jackson and models", "What stays with you"]
    readonly property var wzSubs: root.ru ? ["Эти настройки всегда под рукой: <code>Super + Alt + A</code>, даже на экране входа.", "Язык интерфейса и раскладки клавиатуры. Раскладку переключает Alt + Shift, если не выберешь другое.", "Тема применяется сразу — прямо на этом экране. Передумать можно когда угодно: в центре управления или командой <code>sos theme</code>.", "Пресет можно сменить в любой момент, а Super + T включает плитку только для текущего стола.", "Профиль — только стартовый набор модулей. Любой модуль потом ставится и удаляется одной командой, с откатом: <code>sos modules</code>.", "Нашли видеокарту и подобрали модель, которая в неё влезет. Облако — по желанию: ключи лежат в системной связке, а не в файлах.", "Коротко о приватности, первый снимок системы и клавиши, которые стоит запомнить."] : ["These settings are always one press away: <code>Super + Alt + A</code>, even on the login screen.", "Interface language and keyboard layouts. Alt + Shift switches layouts unless you pick another key.", "The theme applies right away, on this very screen. Change it any time in the control center or with <code>sos theme</code>.", "Switch presets any time; Super + T tiles just the current workspace.", "A profile is just a starter set of modules. Any module installs and uninstalls later with one command, with undo: <code>sos modules</code>.", "We found your graphics card and picked a model that fits it. The cloud is optional: keys live in the system keyring, not in files.", "Privacy in short, the first system snapshot and the keys worth remembering."]

    // step 1
    readonly property string wzMotionSub: root.t("без анимаций, скоп статичен", "no animations, still scope")
    readonly property string wzContrastSub: root.t("для всех тем, текст AAA", "every theme, AAA text")
    readonly property string wzLargeSub: root.t("панели и мастер на 15 % крупнее", "panels and wizard 15% larger")
    readonly property string wzSoundSub: root.t("··· ——— ··· синусом, 1,8 с", "··· ——— ··· in sine, 1.8 s")
    readonly property string wzPostTitle: root.t("Экран POST при входе", "POST screen at login")
    readonly property string wzPostSub: root.t("секунда фактов о машине", "one second of machine facts")
    readonly property string wzIdleTitle: root.t("Блокировать без дела", "Lock when idle")
    function wzIdleSub(min) {
        return min > 0 ? root.t("через " + min + " мин", "after " + min + " min") : root.t("никогда", "never");
    }

    // step 2
    readonly property string wzUiLang: root.t("Язык интерфейса", "Interface language")
    readonly property string wzRuHint: root.t("Интерфейс, Джексон и подсказки по-русски", "Russian interface, Jackson and hints")
    readonly property string wzEnHint: root.t("Интерфейс, Джексон и подсказки по-английски", "English interface, Jackson and hints")
    readonly property string wzLayouts: root.t("Раскладки клавиатуры", "Keyboard layouts")
    readonly property string wzLayoutsHint: root.t("первая — для сочетаний клавиш", "the first one drives shortcuts")
    readonly property string wzSwitchWith: root.t("Переключать", "Switch with")
    readonly property string wzTryHere: root.t("Попробуй переключить раскладку здесь", "Try switching layouts here")
    readonly property var kbNames: ({ us: root.t("Английская", "English"), ru: root.t("Русская", "Russian"), ua: root.t("Украинская", "Ukrainian"), by: root.t("Белорусская", "Belarusian"), kz: root.t("Казахская", "Kazakh"), de: root.t("Немецкая", "German"), fr: root.t("Французская", "French"), es: root.t("Испанская", "Spanish"), pl: root.t("Польская", "Polish"), tr: root.t("Турецкая", "Turkish") })

    // step 3
    readonly property string wzGraphiteSub: root.t("Тёмная, янтарный сигнал", "Dark, amber signal")
    readonly property string wzPaperSub: root.t("Светлая, чернильный синий", "Light, ink blue")
    readonly property string wzAutoSub: root.t("Бумага днём, Графит ночью", "Paper by day, Graphite by night")
    readonly property string wzPhosphorSub: root.t("Зелёный люминофор, для души", "Green phosphor, for the soul")
    readonly property string wzDefault: root.t("по умолчанию", "default")
    readonly property string wzAutoTitle: root.t("Как работает «Авто»", "How «Auto» works")
    readonly property string wzAutoBody: root.t("Место не спрашиваем: по умолчанию 07:00 и 20:00. По закату — только если разрешишь геолокацию.", "We don't ask where you are: 07:00 and 20:00 by default. Sunset times only if you allow location.")
    readonly property string wzNow: root.t("сейчас", "now")
    readonly property string themeGraphite: root.t("Графит", "Graphite")
    readonly property string themePaper: root.t("Бумага", "Paper")
    readonly property string themeAuto: root.t("Авто", "Auto")
    readonly property string themePhosphor: root.t("Фосфор", "Phosphor")

    // step 5
    readonly property string wzOfflineFoot: root.t("дополняет любой профиль", "adds to any profile")
    readonly property string wzGpuFits: root.t("видеокарта подходит", "your GPU fits")
    readonly property string wzGpuShort: root.t("видеокарты мало", "GPU too small")
    readonly property string wzWillInstall: root.t("Будет установлено:", "Will be installed:")
    readonly property string wzBeforeInstall: root.t("Перед установкой — снимок системы.", "A system snapshot comes first.")
    readonly property string wzNothingToInstall: root.t("Ничего не ставим — только основа.", "Nothing to install — just the base.")
    function wzFreeOf(free) {
        return root.t("из " + free + " свободных", "of " + free + " free");
    }
    readonly property string wzApps: root.t("Приложения", "Apps")
    readonly property string wzObsidianSub: root.t("заметки в Markdown · из Flathub · бесплатная, закрытый код", "Markdown notes · from Flathub · free, closed source")
    readonly property string wzAfterSetup: root.t("ставится после настройки, в фоне", "installs after setup, in the background")

    // step 6
    readonly property string wzVram: root.t("видеопамять", "video memory")
    readonly property string wzRam: root.t("ОЗУ", "RAM")
    readonly property string wzCpuOnly: root.t("Без видеокарты — модель работает на процессоре", "No graphics card — the model runs on the CPU")
    readonly property string wzDoctorOk: root.t("GPU Doctor: всё в порядке", "GPU Doctor: all good")
    function wzDoctorIssues(n) {
        return root.t("GPU Doctor: " + n + " " + root.plural(n, "замечание", "замечания", "замечаний"), "GPU Doctor: " + n + (n === 1 ? " issue" : " issues"));
    }
    readonly property string wzModelFor: root.t("Модель для Джексона", "Jackson's model")
    readonly property string wzEstimate: root.t("оценка для твоей видеокарты", "estimated for your GPU")
    readonly property string wzEstimateCpu: root.t("оценка для твоей памяти", "estimated for your memory")
    readonly property string wzFits: root.t("влезет", "fits")
    readonly property string wzTight: root.t("впритык", "tight")
    readonly property string wzNoFit: root.t("не влезет", "won't fit")
    function wzLeftover(v) {
        return root.t("останется " + v, v + " to spare");
    }
    readonly property string wzOffloadNote: root.t("часть слоёв в ОЗУ", "some layers in RAM")
    readonly property string wzTokS: root.t("ток/с", "tok/s")
    readonly property string wzInstallModel: root.t("Установить", "Install")
    readonly property string wzRetry: root.t("Повторить", "Retry")
    readonly property string wzInstalled: root.t("установлена", "installed")
    readonly property string wzDownloadTo: root.t("скачается в /srv/ai · можно продолжать настройку", "downloads to /srv/ai · you can keep going")
    function wzDownloading(done, total) {
        return root.t("скачивается: " + done + " из " + total, "downloading: " + done + " of " + total);
    }
    readonly property string wzNoDisk: root.t("не хватает места на диске", "not enough disk space")
    readonly property string wzNoSuggest: root.t("Подбор модели недоступен: нет команды sos.", "Model suggestions are unavailable: the sos command is missing.")
    readonly property string wzCloud: root.t("Облачные модели", "Cloud models")
    readonly property string wzOptional: root.t("необязательно", "optional")
    readonly property string wzCloudSub: root.t("Без ключей Джексон работает полностью на этом компьютере.", "Without keys Jackson runs entirely on this computer.")
    readonly property string wzAddKey: root.t("Добавить ключ", "Add key")
    readonly property string wzKeyInRing: root.t("ключ в связке", "key in keyring")
    readonly property string wzSave: root.t("Сохранить", "Save")
    readonly property string wzPasteKey: root.t("Вставь ключ API", "Paste the API key")
    readonly property string wzCloudNoteTitle: root.t("В облако — только по твоему слову", "To the cloud only when you say so")
    readonly property string wzCloudNote: root.t("Запрос уходит наружу, если ты выбрал облачную модель или разрешил это для задачи. Каждый такой запрос виден в строке состояния и в журнале, с ценой.", "A request leaves the machine only if you picked a cloud model or allowed it for a task. Every such request shows up in the status line and the log, with its price.")

    // step 7
    readonly property string wzSnapshotTitle: root.t("Первый снимок системы", "First system snapshot")
    readonly property string wzSnapshotSub: root.t("Точка, к которой всегда можно вернуться: Super + Z или «вчерашняя система» в загрузчике.", "A point you can always return to: Super + Z, or «yesterday's system» in the boot menu.")
    readonly property string wzSnapshotButton: root.t("Сделать снимок", "Take snapshot")
    readonly property string wzKeysTitle: root.t("Клавиши, которые стоит запомнить", "Keys worth remembering")
    readonly property string wzQueued: root.t("После настройки поставим:", "After setup we install:")
    readonly property string wzInstallStarted: root.t("Установка модулей началась", "Module installation started")
    readonly property string wzInstallDone: root.t("Модули установлены", "Modules installed")
    readonly property string wzInstallFailed: root.t("Установка модулей не удалась", "Module installation failed")
    readonly property string wzModelDone: root.t("Модель скачана", "Model downloaded")
    readonly property string wzModelFailed: root.t("Модель не скачалась", "Model download failed")
    readonly property string wzUndoHint: root.t("отменить: sos undo", "undo: sos undo")
}
