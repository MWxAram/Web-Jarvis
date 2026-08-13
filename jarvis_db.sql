-- phpMyAdmin SQL Dump
-- version 5.1.2
-- https://www.phpmyadmin.net/
--
-- jarvis_db — ПУБЛИЧНАЯ версия для GitHub.
-- Из оригинальной выгрузки удалены: реальные аккаунты пользователей
-- (email/хеши паролей), реальные refresh-токены, реальные активированные
-- VIP-ключи, реальные подписки и реальное сообщение из формы обратной
-- связи. Оставлены: структура всех таблиц, публичный changelog
-- (`updates` — то, что показывается на сайте), и demo VIP-ключи для теста.

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Таблица `analytics_events`
--

CREATE TABLE `analytics_events` (
  `id` int(11) NOT NULL,
  `event_type` varchar(60) NOT NULL,
  `event_ts` datetime NOT NULL,
  `received_at` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Пусто по умолчанию — реальная телеметрия использования не публикуется.

-- --------------------------------------------------------

--
-- Таблица `contact_messages`
--

CREATE TABLE `contact_messages` (
  `id` int(10) UNSIGNED NOT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `message` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_read` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Пусто по умолчанию — реальные сообщения пользователей не публикуются.

-- --------------------------------------------------------

--
-- Таблица `devices`
--

CREATE TABLE `devices` (
  `id` int(10) UNSIGNED NOT NULL,
  `user_id` int(10) UNSIGNED NOT NULL,
  `device_name` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `hwid` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_seen` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Таблица `license_keys`
--

CREATE TABLE `license_keys` (
  `id` int(10) UNSIGNED NOT NULL,
  `key_value` char(24) NOT NULL,
  `user_id` int(10) UNSIGNED DEFAULT NULL,
  `plan` enum('vip') NOT NULL DEFAULT 'vip',
  `duration_days` smallint(6) NOT NULL DEFAULT '30',
  `activated_at` datetime DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Demo-ключи для теста (не привязаны ни к одному пользователю) —
-- реальные активированные ключи из оригинальной выгрузки удалены.
--

INSERT INTO `license_keys` (`id`, `key_value`, `user_id`, `plan`, `duration_days`, `activated_at`, `expires_at`, `created_at`) VALUES
(1, 'JRVS-DEMO-VIP1-2026', NULL, 'vip', 30, NULL, NULL, '2026-06-15 15:19:37'),
(2, 'JRVS-DEMO-VIP2-2026', NULL, 'vip', 30, NULL, NULL, '2026-06-15 15:19:37'),
(3, 'JRVS-DEMO-VIP3-2026', NULL, 'vip', 90, NULL, NULL, '2026-06-15 15:19:37');

-- --------------------------------------------------------

--
-- Таблица `refresh_tokens`
--

CREATE TABLE `refresh_tokens` (
  `id` int(10) UNSIGNED NOT NULL,
  `user_id` int(10) UNSIGNED NOT NULL,
  `token_hash` char(64) NOT NULL,
  `expires_at` datetime NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Пусто по умолчанию — это активные сессии авторизации, не публикуются.

-- --------------------------------------------------------

--
-- Таблица `subscriptions`
--

CREATE TABLE `subscriptions` (
  `id` int(10) UNSIGNED NOT NULL,
  `user_id` int(10) UNSIGNED NOT NULL,
  `plan` enum('free','vip') NOT NULL DEFAULT 'free',
  `starts_at` datetime DEFAULT NULL,
  `expires_at` datetime DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Пусто по умолчанию — привязано к реальным пользователям, не публикуется.

-- --------------------------------------------------------

--
-- Таблица `updates` — публичный changelog, отображается на сайте.
--

CREATE TABLE `updates` (
  `id` int(10) UNSIGNED NOT NULL,
  `version` varchar(30) NOT NULL,
  `release_date` date NOT NULL,
  `title` varchar(150) NOT NULL,
  `changelog` json NOT NULL,
  `featured` tinyint(1) NOT NULL DEFAULT '0',
  `featured_color` varchar(20) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

--
-- Dumping data for table `updates`
--

INSERT INTO `updates` (`id`, `version`, `release_date`, `title`, `changelog`, `featured`, `featured_color`, `created_at`, `updated_at`) VALUES
(1, 'V0.9.1', '2026-06-12', 'Авто обновление и  VIP', '[{\"tag\": \"new\", \"text\": \"Добавлено авто обновление для автоматического скачивание обновление программы\"}, {\"tag\": \"new\", \"text\": \"Добавлено VIP вкладка для кастомизации за 1$ в месяц\"}, {\"tag\": \"improved\", \"text\": \"Улучшено скорость работы Jarvis\"}]', 0, NULL, '2026-06-20 07:10:54', '2026-08-01 12:13:12'),
(2, 'V0.8.0', '2026-06-03', 'Кнопка стоп', '[{\"tag\": \"new\", \"text\": \"Было добавлено кнопка для остановки разговора Jarvis\"}]', 0, NULL, '2026-06-20 07:15:20', '2026-08-01 12:13:19'),
(3, 'V1.0.0', '2026-06-30', 'Локальные команды и не большие исправление', '[{\"tag\": \"new\", \"text\": \"Было добавлены локальные команды которые выполняются в самом Jarvis благодаря которому ответ поступает намного быстрее и не тратится токены ИИ\"}, {\"tag\": \"fixed\", \"text\": \"Не большие исправление багов\"}, {\"tag\": \"improved\", \"text\": \"Увеличено скорость ответа Jarvis и общая скорость работы\"}, {\"tag\": \"improved\", \"text\": \"Улучшено скорость запуска Jarvis\"}]', 0, NULL, '2026-06-20 07:19:52', '2026-08-13 11:26:18'),
(4, 'V1.0.1', '2026-07-01', 'Чувствительность микрофона и Автор программы', '[{\"tag\": \"fixed\", \"text\": \"Исправлено что Джарвис не слышал микрофон с маленькой чувствительностью теперь он адаптируется под чувствительность микрофона\"}, {\"tag\": \"new\", \"text\": \"Добавлено новая вкладка в Настройках Джарвис где имеется информация о разработчике\"}]', 1, '#ffd24a', '2026-06-27 12:36:45', '2026-08-01 12:13:33'),
(5, 'V1.0.4', '2026-08-01', 'Улучшение безопасности и сбор анонимно данных', '[{\"tag\": \"new\", \"text\": \"Теперь для разработчиков анонимно собираются данные без текста какие функции используются больше всего\"}, {\"tag\": \"improved\", \"text\": \"Улучшено скорость ответа Джарвис\"}, {\"tag\": \"fixed\", \"text\": \"Исправлены ошибки в безопасности\"}, {\"tag\": \"fixed\", \"text\": \"Исправлены некоторые баги\"}, {\"tag\": \"new\", \"text\": \"Теперь все ошибки из теримнала которые не видны пользователю сохраняются в отдельном файле\"}, {\"tag\": \"new\", \"text\": \"Джарвис теперь знает больше информации про себя и отвечает более точно\"}]', 1, '#00ffa8', '2026-08-01 12:12:47', '2026-08-01 12:13:25'),
(6, 'V1.1.0', '2026-08-13', 'Создание установщика и не большие изменение', '[{\"tag\": \"new\", \"text\": \"Был создан установщик для удобного скачивание Jarvis.\"}, {\"tag\": \"fixed\", \"text\": \"Исправлены не большие баги\"}, {\"tag\": \"improved\", \"text\": \"Теперь есть возможность выбирать микрофон\"}, {\"tag\": \"improved\", \"text\": \"Теперь в настройках имеется возможность выбрать запускать Jarvis с Windows.\"}]', 1, '#ff5eeb', '2026-08-13 11:26:04', '2026-08-13 11:26:33');

-- --------------------------------------------------------

--
-- Таблица `users`
--

CREATE TABLE `users` (
  `id` int(10) UNSIGNED NOT NULL,
  `username` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `password_hash` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  `is_admin` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `last_seen_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Пусто по умолчанию — реальные аккаунты (email + хеш пароля) не
-- публикуются. Первый зарегистрированный пользователь становится обычным
-- аккаунтом; is_admin выставляется вручную в БД при необходимости.

--
-- Индексы сохранённых таблиц
--

--
-- Индексы таблицы `analytics_events`
--
ALTER TABLE `analytics_events`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ix_analytics_events_event_ts` (`event_ts`),
  ADD KEY `ix_analytics_events_event_type` (`event_type`);

--
-- Индексы таблицы `contact_messages`
--
ALTER TABLE `contact_messages`
  ADD PRIMARY KEY (`id`),
  ADD KEY `idx_unread` (`is_read`);

--
-- Индексы таблицы `devices`
--
ALTER TABLE `devices`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `uq_user_hwid` (`user_id`,`hwid`),
  ADD KEY `idx_user_devices` (`user_id`);

--
-- Индексы таблицы `license_keys`
--
ALTER TABLE `license_keys`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `key_value` (`key_value`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `idx_key` (`key_value`);

--
-- Индексы таблицы `refresh_tokens`
--
ALTER TABLE `refresh_tokens`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `token_hash` (`token_hash`),
  ADD KEY `idx_user_tokens` (`user_id`);

--
-- Индексы таблицы `subscriptions`
--
ALTER TABLE `subscriptions`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `user_id` (`user_id`);

--
-- Индексы таблицы `updates`
--
ALTER TABLE `updates`
  ADD PRIMARY KEY (`id`);

--
-- Индексы таблицы `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`),
  ADD UNIQUE KEY `email` (`email`),
  ADD KEY `idx_email` (`email`),
  ADD KEY `idx_last_seen` (`last_seen_at`);

--
-- AUTO_INCREMENT для сохранённых таблиц
--

ALTER TABLE `analytics_events`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1;

ALTER TABLE `contact_messages`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1;

ALTER TABLE `devices`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT;

ALTER TABLE `license_keys`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

ALTER TABLE `refresh_tokens`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1;

ALTER TABLE `subscriptions`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1;

ALTER TABLE `updates`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

ALTER TABLE `users`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=1;

--
-- Ограничения внешних ключей
--

ALTER TABLE `devices`
  ADD CONSTRAINT `devices_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

ALTER TABLE `license_keys`
  ADD CONSTRAINT `license_keys_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL;

ALTER TABLE `refresh_tokens`
  ADD CONSTRAINT `refresh_tokens_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

ALTER TABLE `subscriptions`
  ADD CONSTRAINT `subscriptions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
