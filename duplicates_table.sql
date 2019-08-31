CREATE TABLE duplicates (
    image_id SERIAL,
    group_id BIGINT NOT NULL,
    filename TEXT NOT NULL,
    directory_name TEXT NOT NULL,
    keep BOOLEAN NOT NULL,
    modified_time TIMESTAMP NOT NULL,
    picture_taken_time TIMESTAMP
);