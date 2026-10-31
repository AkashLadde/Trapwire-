-- ===================================================================
-- TRAPWIRE — Comprehensive MySQL Database Schema
-- Digital Personal Data Protection (DPDP) Act, 2023 Compliance &
-- Intrusion Deception Architecture
-- ===================================================================

CREATE DATABASE IF NOT EXISTS `trapwire_db`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `trapwire_db`;

-- 1. E-Commerce Orders & Customer Profiles
CREATE TABLE IF NOT EXISTS `orders` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `order_id` VARCHAR(32) NOT NULL UNIQUE,
  `customer_name` VARCHAR(128) NOT NULL,
  `phone` VARCHAR(32),
  `email` VARCHAR(128),
  `aadhaar` VARCHAR(32),
  `pan` VARCHAR(32),
  `address` TEXT,
  `card_last4` VARCHAR(16),
  `item` VARCHAR(128),
  `order_value` DECIMAL(10, 2),
  `status` VARCHAR(32) DEFAULT 'Pending',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Live Security Alerts & Anomaly Telemetry
CREATE TABLE IF NOT EXISTS `alerts` (
  `id` VARCHAR(32) PRIMARY KEY,
  `message` TEXT NOT NULL,
  `level` VARCHAR(16) NOT NULL,
  `timestamp` DOUBLE NOT NULL,
  `meta_json` TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Incident Response & Breach Records
CREATE TABLE IF NOT EXISTS `incidents` (
  `incident_id` VARCHAR(32) PRIMARY KEY,
  `attacker_ip` VARCHAR(64),
  `attacker_isp` VARCHAR(128),
  `detected_at` DOUBLE,
  `status` VARCHAR(32),
  `stage` VARCHAR(32),
  `ack_number` VARCHAR(64)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Canary Tracking Tokens & Phone-Home Beacons
CREATE TABLE IF NOT EXISTS `canary_hits` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `token` VARCHAR(64) NOT NULL,
  `ip` VARCHAR(64),
  `isp` VARCHAR(128),
  `user_agent` TEXT,
  `triggered_at` DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Auto-Submitted DPB Compliance Reports
CREATE TABLE IF NOT EXISTS `submitted_reports` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `incident_id` VARCHAR(32) NOT NULL,
  `stage` VARCHAR(32) NOT NULL,
  `filename` VARCHAR(255) NOT NULL,
  `ack_number` VARCHAR(64) NOT NULL,
  `ack_status` VARCHAR(32) NOT NULL,
  `submitted_at` DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. Team Members & Administration Roles
CREATE TABLE IF NOT EXISTS `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(128) NOT NULL,
  `email` VARCHAR(128) NOT NULL UNIQUE,
  `role` VARCHAR(64) DEFAULT 'Analyst',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. Admin Emergency SMS Notifications
CREATE TABLE IF NOT EXISTS `sms_audit` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `recipient` VARCHAR(32) NOT NULL,
  `message` TEXT NOT NULL,
  `status` VARCHAR(32) DEFAULT 'DISPATCHED',
  `sent_at` DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Seed initial team users
INSERT INTO `users` (`name`, `email`, `role`) VALUES
('Aditi Rao', 'aditi.rao@trapwire.co.in', 'Security Lead'),
('Rohan Mehta', 'rohan.mehta@trapwire.co.in', 'Compliance Officer'),
('Kavya Sharma', 'kavya.s@trapwire.co.in', 'SOC Analyst')
ON DUPLICATE KEY UPDATE `role`=VALUES(`role`);
