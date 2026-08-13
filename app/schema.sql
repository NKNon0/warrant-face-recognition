CREATE DATABASE IF NOT EXISTS Face_Ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE Face_Ai;

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  telegram_id BIGINT UNIQUE,
  username VARCHAR(255),
  first_name VARCHAR(255),
  is_authorized BOOLEAN DEFAULT FALSE,
  role VARCHAR(50) DEFAULT 'user',
  rank_title VARCHAR(100),
  police_station VARCHAR(255),
  phone_number VARCHAR(50),
  badge_id VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS media_requests (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT,
  telegram_message_id BIGINT,
  media_file_id VARCHAR(255),
  media_type VARCHAR(50),
  status VARCHAR(50),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS face_profiles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  person_name VARCHAR(255),
  id_number VARCHAR(50),
  detail TEXT,
  station VARCHAR(500),
  court VARCHAR(500),
  source VARCHAR(255),
  face_embedding JSON,
  photo_url VARCHAR(500),
  metadata JSON,
  found_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS license_plates (
  id INT AUTO_INCREMENT PRIMARY KEY,
  plate_text VARCHAR(255) NOT NULL,
  province VARCHAR(100),
  detail TEXT,
  station VARCHAR(255),
  category VARCHAR(100),
  plate_image_url VARCHAR(500),
  metadata JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS id_cards (
  id INT AUTO_INCREMENT PRIMARY KEY,
  id_number VARCHAR(50) NOT NULL,
  name VARCHAR(255),
  birthdate DATE,
  address TEXT,
  card_image_url VARCHAR(500),
  metadata JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_results (
  id INT AUTO_INCREMENT PRIMARY KEY,
  request_id INT,
  result_type VARCHAR(50),
  match_score FLOAT,
  matched_record_id INT,
  details JSON,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
