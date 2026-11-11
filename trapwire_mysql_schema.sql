-- ===================================================================
-- TRAPWIRE — MySQL Database Schema
-- Digital Personal Data Protection (DPDP) Act, 2023 Compliance &
-- Intrusion Deception Architecture
-- Note: Schema only — no hardcoded/dummy records are seeded here.
-- To optionally load synthetic demo records, run: python seed_sample_data.py
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
  `attacker_location` VARCHAR(128),
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
  `city` VARCHAR(64),
  `country` VARCHAR(64),
  `user_agent` TEXT,
  `screen` VARCHAR(32),
  `timezone` VARCHAR(64),
  `language` VARCHAR(32),
  `platform` VARCHAR(64),
  `cores` VARCHAR(32),
  `triggered_at` DOUBLE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Auto-Submitted DPB Compliance Reports
CREATE TABLE IF NOT EXISTS `submitted_reports` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `incident_id` VARCHAR(32) NOT NULL,
  `stage` VARCHAR(32) NOT NULL,
  `filename` VARCHAR(255) NOT NULL,
  `ack_number` VARCHAR(64) NOT NULL UNIQUE,
  `ack_status` VARCHAR(32) NOT NULL,
  `attacker_ip` VARCHAR(64),
  `attacker_isp` VARCHAR(128),
  `detected_at` DOUBLE,
  `submitted_at` DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. Team Members & Administration Roles
CREATE TABLE IF NOT EXISTS `users` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(128) NOT NULL,
  `email` VARCHAR(128) NOT NULL UNIQUE,
  `role` VARCHAR(64) DEFAULT 'Analyst',
  `status` VARCHAR(32) DEFAULT 'Active',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7. Enterprise Projects
CREATE TABLE IF NOT EXISTS `projects` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(128) NOT NULL,
  `client` VARCHAR(128) NOT NULL,
  `owner` VARCHAR(128) NOT NULL,
  `deadline` VARCHAR(32),
  `budget` DECIMAL(12, 2) DEFAULT 0,
  `progress` INT DEFAULT 0,
  `status` VARCHAR(32) DEFAULT 'Planning',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8. Alert Dispatch Audit Log
CREATE TABLE IF NOT EXISTS `sms_audit` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `recipient` VARCHAR(32) NOT NULL,
  `message` TEXT NOT NULL,
  `status` VARCHAR(32) DEFAULT 'DISPATCHED',
  `sent_at` DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
