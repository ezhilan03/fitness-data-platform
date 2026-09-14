-- Values and unit/timezone normalization were validated by the ingestion contract.
-- Retain both knowledge timestamps so model training views cannot see future data.
select * from {{ source('fitness_raw', 'revisions') }}
where available_at <= {{ cutoff() }} and received_at <= {{ cutoff() }}
