# DATA.md

All data in this directory is synthetic. Names of sites, investigators, and trial identifiers are invented.

## data/sites.csv

| Column | Type | Meaning |
|---|---|---|
| `site_id` | string | Unique site identifier |
| `site_name` | string | Name of the hospital or research center |
| `country` | string | Country where the site is located |
| `city` | string | City where the site is located |
| `region` | string | Geographic region |
| `therapeutic_areas` | string | Pipe-separated therapeutic areas |
| `indication_experience` | string | Pipe-separated indications previously studied at the site |
| `historical_patients_per_month` | float | Historical average patients enrolled per month |
| `avg_activation_days` | integer | Average days from selection to site activation |
| `data_quality_score` | float | Data quality metric from 0 to 1 |
| `active_trials` | integer | Number of trials currently active at the site |
| `beds` | integer | Number of beds available for clinical research use |
| `has_biomarker_testing` | boolean | Whether the site has on-site biomarker testing capability |
| `has_pediatric_capability` | boolean | Whether the site can enroll pediatric participants |
| `principal_investigator` | string | Name of the principal investigator |
| `last_active_date` | date | Date the site was last active on a trial |

## data/past_trials.csv

| Column | Type | Meaning |
|---|---|---|
| `trial_id` | string | Unique trial identifier |
| `site_id` | string | Site that participated in the trial |
| `indication` | string | Indication studied |
| `phase` | string | Trial phase |
| `planned_enrollment` | integer | Planned number of participants at the site |
| `actual_enrollment` | integer | Actual number of participants enrolled at the site |
| `months_to_target` | float | Months taken to reach target enrollment |
| `screen_failure_rate` | float | Fraction of screened participants who failed screening |
| `start_date` | date | Trial start date at the site |
| `end_date` | date | Trial end date at the site |

## data/competing_trials.csv

| Column | Type | Meaning |
|---|---|---|
| `indication` | string | Indication under competition |
| `country` | string | Country of competition |
| `phase` | string | Trial phase |
| `active_trial_count` | integer | Number of active competing trials |
| `estimated_patient_demand` | integer | Estimated patient demand across competing trials |
| `as_of_date` | date | Snapshot date for the row |

## data/country_stats.csv

| Column | Type | Meaning |
|---|---|---|
| `country` | string | Country name |
| `indication` | string | Indication |
| `prevalence_per_100k` | float | Estimated prevalence per 100,000 population |
| `population_millions` | float | Population in millions |
| `avg_regulatory_approval_days` | integer | Average days for regulatory approval |
| `avg_ethics_approval_days` | integer | Average days for ethics committee approval |
