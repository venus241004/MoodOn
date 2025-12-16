-- db/schema.sql

CREATE DATABASE IF NOT EXISTS moodon
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE moodon;

-- 1) 사용자
CREATE TABLE `user` (
  user_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  email       VARCHAR(255) NOT NULL UNIQUE,
  password    VARCHAR(255) NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2) 채팅 세션
CREATE TABLE chat_session (
  chat_session_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id         INT UNSIGNED NOT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (chat_session_id),
  KEY idx_chat_session_user (user_id),
  CONSTRAINT fk_chat_session_user
    FOREIGN KEY (user_id) REFERENCES `user`(user_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3) 채팅 메시지
CREATE TABLE chat_message (
  chat_message_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  chat_session_id INT UNSIGNED NOT NULL,
  content         TEXT NOT NULL,
  role            ENUM('user', 'bot') NOT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (chat_message_id),
  KEY idx_chat_message_session (chat_session_id),
  CONSTRAINT fk_chat_message_session
    FOREIGN KEY (chat_session_id) REFERENCES chat_session(chat_session_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4) 피드백 (좋아요/별로예요 등)
CREATE TABLE feedback (
  feedback_id     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  chat_message_id INT UNSIGNED NOT NULL,
  feedback        BOOLEAN NOT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (feedback_id),
  KEY idx_feedback_message (chat_message_id),
  CONSTRAINT fk_feedback_message
    FOREIGN KEY (chat_message_id) REFERENCES chat_message(chat_message_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5) 상품 카테고리
CREATE TABLE product_category (
  category_id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  category_name VARCHAR(64) NOT NULL UNIQUE,
  PRIMARY KEY (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6) 무드
CREATE TABLE mood (
  mood_id    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  mood_name  VARCHAR(64) NOT NULL UNIQUE,
  PRIMARY KEY (mood_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 7) 상품 기본 정보
-- JSON의 product_id("guud_97008")는 source_product_id로 저장
CREATE TABLE product (
  product_id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_product_id VARCHAR(64) NOT NULL UNIQUE,
  category_id       INT UNSIGNED NOT NULL,
  brand_name        VARCHAR(128) NOT NULL,
  product_name      VARCHAR(255) NOT NULL,
  link_url          VARCHAR(512),
  image_url         VARCHAR(512),
  s3_path           VARCHAR(512),
  s3_url            VARCHAR(512),
  price             INT UNSIGNED,
  created_at        DATE,
  PRIMARY KEY (product_id),
  KEY idx_product_category (category_id),
  CONSTRAINT fk_product_category
    FOREIGN KEY (category_id) REFERENCES product_category(category_id)
    ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 8) 상품-무드 매핑
CREATE TABLE product_mood (
  product_mood_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_id      INT UNSIGNED NOT NULL,
  mood_id         INT UNSIGNED NOT NULL,
  PRIMARY KEY (product_mood_id),
  UNIQUE KEY uq_product_mood (product_id, mood_id),
  KEY idx_product_mood_product (product_id),
  KEY idx_product_mood_mood (mood_id),
  CONSTRAINT fk_product_mood_product
    FOREIGN KEY (product_id) REFERENCES product(product_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_product_mood_mood
    FOREIGN KEY (mood_id) REFERENCES mood(mood_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 9) 상품 상세 JSON (리뷰, mood_keywords 등 통으로 저장)
CREATE TABLE product_detail (
  product_detail_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  product_id        INT UNSIGNED NOT NULL,
  parsed_json       JSON NOT NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (product_detail_id),
  UNIQUE KEY uq_product_detail_product (product_id),
  CONSTRAINT fk_product_detail_product
    FOREIGN KEY (product_id) REFERENCES product(product_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 10) 추천 기록 (어떤 메시지에 어떤 상품을 추천했는지)
CREATE TABLE recommendation (
  recommendation_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  chat_message_id   INT UNSIGNED NOT NULL,
  product_id        INT UNSIGNED NOT NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (recommendation_id),
  KEY idx_recommendation_message (chat_message_id),
  KEY idx_recommendation_product (product_id),
  CONSTRAINT fk_recommendation_message
    FOREIGN KEY (chat_message_id) REFERENCES chat_message(chat_message_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_recommendation_product
    FOREIGN KEY (product_id) REFERENCES product(product_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 11) 위시리스트
CREATE TABLE wishlist_item (
  wishlist_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id     INT UNSIGNED NOT NULL,
  product_id  INT UNSIGNED NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (wishlist_id),
  UNIQUE KEY uq_wishlist_user_product (user_id, product_id),
  KEY idx_wishlist_user (user_id),
  KEY idx_wishlist_product (product_id),
  CONSTRAINT fk_wishlist_user
    FOREIGN KEY (user_id) REFERENCES `user`(user_id)
    ON DELETE CASCADE,
  CONSTRAINT fk_wishlist_product
    FOREIGN KEY (product_id) REFERENCES product(product_id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
