-- Normative analytical shape, to be integrated by Codex. Raw storage remains immutable.
CREATE TABLE search_request (
 snapshot_id VARCHAR, request_id VARCHAR, query_raw VARCHAR, source_file VARCHAR, source_line BIGINT,
 time_index_raw VARCHAR, split_raw VARCHAR, PRIMARY KEY(snapshot_id,request_id)
);
CREATE TABLE request_item_pair (
 snapshot_id VARCHAR, request_id VARCHAR, item_id VARCHAR,
 impressed BOOLEAN, clicked BOOLEAN, purchased BOOLEAN,
 PRIMARY KEY(snapshot_id,request_id,item_id)
);
CREATE TABLE item_metadata (
 snapshot_id VARCHAR, item_id VARCHAR, item_title VARCHAR,
 category_level1_id VARCHAR, category_level1_name VARCHAR,
 source_file VARCHAR, source_line BIGINT, PRIMARY KEY(snapshot_id,item_id)
);
-- Example: exposed pair denominator; the product function must add a validated scope filter.
-- SELECT sum(CASE WHEN impressed THEN 1 ELSE 0 END) AS E,
--        sum(CASE WHEN impressed AND clicked THEN 1 ELSE 0 END) AS C,
--        sum(CASE WHEN impressed AND purchased THEN 1 ELSE 0 END) AS P
-- FROM request_item_pair WHERE snapshot_id=?;
