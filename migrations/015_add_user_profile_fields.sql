ALTER TABLE users ADD COLUMN about TEXT CHECK(char_length(about) <= 4096);
ALTER TABLE users ADD COLUMN link VARCHAR(2000);
