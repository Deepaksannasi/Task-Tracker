-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Dec 12, 2025 at 05:32 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.0.30

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `task`
--

-- --------------------------------------------------------

--
-- Table structure for table `tasks`
--

CREATE TABLE `tasks` (
  `id` int(10) UNSIGNED NOT NULL,
  `user_id` int(10) UNSIGNED NOT NULL,
  `title` varchar(255) NOT NULL,
  `description` text DEFAULT NULL,
  `status` enum('Pending','In-Progress','Completed') NOT NULL DEFAULT 'Pending',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `due_date` date DEFAULT NULL,
  `reminder_sent` tinyint(1) DEFAULT 0,
  `priority` enum('low','medium','high','urgent') DEFAULT 'medium'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `tasks`
--

INSERT INTO `tasks` (`id`, `user_id`, `title`, `description`, `status`, `created_at`, `updated_at`, `due_date`, `reminder_sent`, `priority`) VALUES
(21, 1, 'Complete project report', 'Prepare the final project report for submission.', 'In-Progress', '2025-12-11 17:28:25', '2025-12-12 02:49:57', '2025-12-15', 0, 'medium'),
(22, 1, 'Fix login page bug', 'Resolve the authentication error in the login module.', 'In-Progress', '2025-12-11 17:28:25', '2025-12-11 17:28:25', '2025-12-10', 0, 'urgent'),
(23, 2, 'Database backup', 'Weekly backup completed successfully.', 'Completed', '2025-12-11 17:28:25', '2025-12-11 17:28:25', '2025-12-05', 0, 'medium'),
(24, 3, 'Team meeting preparation', 'Prepare agenda and materials for the meeting.', 'Pending', '2025-12-11 17:28:25', '2025-12-12 04:25:45', '2025-12-13', 0, 'low'),
(25, 2, 'Prepare presentation slides', 'Slides for monthly review meeting.', 'Pending', '2025-12-11 17:28:25', '2025-12-11 17:28:25', '2025-12-20', 1, 'medium'),
(26, 1, 'exam', 'exam', 'Pending', '2025-12-12 02:45:47', '2025-12-12 03:03:55', '2025-12-04', 0, 'high');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(10) UNSIGNED NOT NULL,
  `name` varchar(150) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `api_token` varchar(255) DEFAULT NULL,
  `token_created` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `reset_token` varchar(64) DEFAULT NULL,
  `reset_token_expiry` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`id`, `name`, `email`, `password_hash`, `api_token`, `token_created`, `created_at`, `reset_token`, `reset_token_expiry`) VALUES
(1, 'surya', 'surya@gmail.com', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '3cc12e1bbd16975b1cb78b8ea8836171f9dc9596bdf6b9f8093305de83c57af3', '2025-12-11 13:57:06', '2025-12-10 17:37:52', NULL, NULL),
(2, 'Test User', 'test@gmail.com', 'ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae', '8b21a039a90fda155a7806a2c59d13ece96e2c04bc87397015f2a5926e1d0922', '2025-12-10 18:55:00', '2025-12-10 18:49:59', NULL, NULL),
(3, 'DEEPAKKUMAR', 'deepaknavin321@gmail.com', 'a28e6ab1b97656b97ad59efa5e42e5dd21d845e9bc247d305004fe835596fdb7', 'ab3145ebc9ceabb00424cff1ce30def4d1f63780b98b94d0ebd9f129a2268c43', '2025-12-11 16:23:19', '2025-12-10 19:11:54', 'b665a2e8f89b70b623f5d045103e1c2930c1c10d5062b7e31923599b6ef9f4e8', NULL);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `tasks`
--
ALTER TABLE `tasks`
  ADD PRIMARY KEY (`id`),
  ADD KEY `user_id` (`user_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `email` (`email`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `tasks`
--
ALTER TABLE `tasks`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=27;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(10) UNSIGNED NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `tasks`
--
ALTER TABLE `tasks`
  ADD CONSTRAINT `tasks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
