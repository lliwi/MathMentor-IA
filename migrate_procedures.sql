-- Migration script to add procedure selection fields
-- Run this on existing databases to upgrade them

-- Add procedure fields to exercises table
ALTER TABLE exercises 
ADD COLUMN IF NOT EXISTS available_procedures JSON,
ADD COLUMN IF NOT EXISTS expected_procedures JSON;

-- Add procedure field to submissions table
ALTER TABLE submissions 
ADD COLUMN IF NOT EXISTS selected_procedures JSON;

-- Add comments for documentation
COMMENT ON COLUMN exercises.available_procedures IS 'List of all available procedures/techniques for this exercise';
COMMENT ON COLUMN exercises.expected_procedures IS 'List of procedure IDs that should be selected for correct methodology';
COMMENT ON COLUMN submissions.selected_procedures IS 'List of procedure IDs selected by the student';

-- Verify changes
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'exercises' 
AND column_name LIKE '%procedure%';

SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'submissions' 
AND column_name LIKE '%procedure%';
