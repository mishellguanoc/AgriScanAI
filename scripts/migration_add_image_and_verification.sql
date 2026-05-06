-- Migration: Add image_path to file_upload and cross-validation fields to diagnosis_result
-- Run this against your Supabase PostgreSQL database.

-- 1. Store image file path alongside the upload record
ALTER TABLE file_upload ADD COLUMN IF NOT EXISTS image_path VARCHAR(512);

-- 2. Track whether the crop-type classifier confirmed the specialist worker's crop type
ALTER TABLE diagnosis_result ADD COLUMN IF NOT EXISTS crop_type_verified BOOLEAN DEFAULT FALSE;

-- 3. Store the crop-type classifier's actual prediction for reinforcement learning review
ALTER TABLE diagnosis_result ADD COLUMN IF NOT EXISTS router_crop_prediction VARCHAR(50);
