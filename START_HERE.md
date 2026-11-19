# START HERE — простой путь без инженерных знаний

## 1. Посмотреть проект прямо сейчас (0 минут)

Открой в браузере:

**http://127.0.0.1:8788/**

Это локальная панель. Ничего устанавливать не нужно.
Если страница не открылась — сервер выключен; скажи мне, я запущу.

## 2. Выложить в интернет — самый простой путь (Render, ~15 минут)

Нужны: аккаунт GitHub и банковская карта (Render платный, ~$7–14/мес).
Render — сайт, который сам запускает Docker-образ и даёт ссылку.

### Шаг 1. Открой Render

https://dashboard.render.com/register

Зарегистрируйся через GitHub.

### Шаг 2. Сделай образ публичным (1 минута)

Открой:

https://github.com/users/vanya9554-del/packages/container/swarm-lab/settings

Прокрути вниз → **Danger Zone** → **Change visibility** → **Public** → подтверди.
Без этого Render не сможет скачать образ.

### Шаг 3. Создай базу данных

В Render нажми **New +** → **Postgres**:

- Name: `swarmlab-db`
- Database: `swarm`
- User: `swarm`
- Plan: самый дешёвый
- Create Database

После создания открой базу → скопируй **Internal Database URL**.
Выглядит как `postgres://...` — это нормально.

### Шаг 4. Создай веб-сервис

В Render нажми **New +** → **Web Service** → вкладка **Deploy an existing image**.

- Image URL: `ghcr.io/vanya9554-del/swarm-lab:v11.20.0`
- Name: `swarmlab`
- Region: ближайший
- Plan: самый дешёвый
- Health Check Path: `/ready`
- Create Web Service

### Шаг 5. Добавь переменные

В созданном сервисе открой **Environment** → **Add Environment Variable**:

| Key | Value |
|---|---|
| `SWARMLAB_DB` | вставь **Internal Database URL** из шага 3 |
| `SWARMLAB_TOKEN` | придумай длинный пароль (например, 40 случайных символов) |

Нажми **Save Changes**. Render перезапустит сервис.

### Шаг 6. Открой ссылку

Через 1–2 минуты сверху будет ссылка вида:

`https://swarmlab-xxxx.onrender.com`

Открой её — увидишь панель. API требует заголовок:

`Authorization: Bearer <твой SWARMLAB_TOKEN>`

Всё. Это уже работает в интернете.

## 3. Если нужен «настоящий» Kubernetes

Это сложнее (нужны аккаунт Google/AWS/Azure и карта). Пошагово:

**https://github.com/vanya9554-del/swarm-lab/blob/main/PRODUCTION.md**

Там кнопки в консоли, команды и проверки. Могу провести тебя по шагам, если скажешь, какой провайдер.

## 4. Пентест (проверка безопасности)

Это **не сайт с кнопкой** — нужен человек/компания, которая проверит систему.
Что уже есть бесплатно и автоматически — в CI (ZAP, bandit, Trivy, pip-audit).

Что делать тебе:

1. Открой **https://github.com/vanya9554-del/swarm-lab/blob/main/PENTEST.md**
2. Если хочешь заказать — найди в поиске «пентест API заказать» или «application security audit».
3. Дай им ссылку на staging и тестовый токен.

Если пентест не нужен сейчас — пропусти, это не блокирует запуск.

## 5. KMS (хранилище ключей)

Нужен только если компания требует облачный KMS.

- AWS: https://console.aws.amazon.com/kms
- Google: https://console.cloud.google.com/security/kms
- Vault: https://developer.hashicorp.com/vault

Если ничего не понятно — не открывай. В проекте уже есть безопасное хранение секретов в Render/K8s; KMS — опция для крупных компаний.

## 6. Что мне присылать, если хочешь, чтобы я делал сам

Достаточно одного из вариантов:

1. **Render API Key**: Render → Account Settings → API Keys → Create; пришли мне ключ.
   Я сам создам базу и сервис через API.
2. **Kubeconfig** от кластера (файл) — я сам задеплою Helm.
3. Или просто напиши «делай через Render», и я буду говорить, куда нажимать.

Ничего из этого не публикуй в открытых чатах; присылай только сюда.
