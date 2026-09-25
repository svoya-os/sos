/* SOS installer slideshow (Calamares slideshow API 1), RU/EN, Graphite palette.
 * SPDX-License-Identifier: Apache-2.0
 * The language the user picked on the welcome page decides which text is primary;
 * the other language is shown underneath, so every slide is readable either way. */
import QtQuick 2.15
import calamares.slideshow 1.0

Presentation {
    id: presentation

    readonly property bool ru: Qt.locale().name.substring(0, 2) === "ru"
    readonly property color wall: "#0c0d0f"
    readonly property color text: "#ebe8e1"
    readonly property color textDim: "#9d9a92"
    readonly property color textFaint: "#67655f"
    readonly property color accent: "#ffb547"

    Timer {
        interval: 9000
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }

    component MorseMark: Row {
        spacing: 7
        Repeater {
            model: [0, 0, 0, 1, 1, 1, 0, 0, 0]
            Rectangle {
                width: modelData ? 24 : 8
                height: 8
                radius: 4
                color: modelData ? presentation.accent : presentation.text
            }
        }
    }

    component SosSlide: Slide {
        id: slide
        property string titleEn
        property string titleRu
        property string bodyEn
        property string bodyRu
        property string meta

        Rectangle {
            anchors.fill: parent
            color: presentation.wall
        }
        Column {
            anchors.left: parent.left
            anchors.leftMargin: 56
            anchors.right: parent.right
            anchors.rightMargin: 56
            anchors.verticalCenter: parent.verticalCenter
            spacing: 18

            MorseMark {}
            Text {
                width: parent.width
                text: presentation.ru ? slide.titleRu : slide.titleEn
                color: presentation.text
                font.family: "IBM Plex Sans"
                font.pixelSize: 28
                font.weight: Font.Light
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: presentation.ru ? slide.bodyRu : slide.bodyEn
                color: presentation.textDim
                font.family: "IBM Plex Sans"
                font.pixelSize: 15
                lineHeight: 1.45
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: presentation.ru ? slide.titleEn + " — " + slide.bodyEn : slide.titleRu + " — " + slide.bodyRu
                color: presentation.textFaint
                font.family: "IBM Plex Sans"
                font.pixelSize: 12
                wrapMode: Text.WordWrap
            }
            Text {
                visible: slide.meta.length > 0
                text: slide.meta
                color: presentation.accent
                font.family: "IBM Plex Mono"
                font.pixelSize: 12
                font.letterSpacing: 1.6
            }
        }
    }

    SosSlide {
        titleEn: "Your own system for AI"
        titleRu: "Своя система для ИИ"
        bodyEn: "Local first and under your control. No ads, no account, no telemetry."
        bodyRu: "Всё локально и под вашим контролем. Без рекламы, аккаунтов и телеметрии."
        meta: "SOS 26.10 · ПЕРВЫЙ СИГНАЛ"
    }
    SosSlide {
        titleEn: "Jackson is one key away"
        titleRu: "Джексон — на расстоянии одной клавиши"
        bodyEn: "Press Super+J. Jackson asks before anything risky, shows what left the machine and can undo its own actions."
        bodyRu: "Нажмите Super+J. Джексон спрашивает перед рискованными действиями, показывает, что ушло в сеть, и умеет отменять свои действия."
        meta: "SUPER + J"
    }
    SosSlide {
        titleEn: "A GPU that just works"
        titleRu: "Видеокарта, которая просто работает"
        bodyEn: "Signed NVIDIA drivers are installed from this medium: no internet, no key enrollment, Secure Boot stays on."
        bodyRu: "Подписанные драйверы NVIDIA ставятся прямо с носителя: без интернета и без регистрации ключей, Secure Boot остаётся включённым."
        meta: "SOS DOCTOR"
    }
    SosSlide {
        titleEn: "Undo everything"
        titleRu: "Отменить можно всё"
        bodyEn: "Btrfs snapshots before every update and change. Super+Z undoes the last one; yesterday's system is an entry in the boot menu."
        bodyRu: "Снимки btrfs перед каждым обновлением и изменением. Super+Z отменяет последнее, а вчерашняя система — пункт в меню загрузки."
        meta: "SUPER + Z"
    }
    SosSlide {
        titleEn: "Modules, not bloat"
        titleRu: "Модули вместо лишнего"
        bodyEn: "Pick a profile in the first-run wizard. Local LLMs, Studio, ML Lab and Agents install later, and one model store is shared by every tool."
        bodyRu: "Выберите профиль при первом запуске. Локальные модели, Студия, ML-лаборатория и агенты ставятся потом, а хранилище моделей общее для всех."
        meta: "/SRV/AI"
    }
}
