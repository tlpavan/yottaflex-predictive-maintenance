# AI Usage and My Contribution

## How I Used ChatGPT

I used ChatGPT as my AI development partner while building this project. I started by understanding the requirements and identifying what the solution needed to achieve. I already had a foundation in programming and data handling, so I used ChatGPT to explore better approaches, clarify concepts, and speed up the development process.

I did not want to spend unnecessary time figuring out every implementation detail through trial and error. Whenever I came across something unfamiliar or needed another perspective, I discussed it with ChatGPT, understood the suggested approach, and used that guidance to move forward.

## My Role in the Project

I was actively involved throughout the development process. I decided what needed to be done, worked through the project requirements, ran the implementation locally, and checked the generated results.

My work included understanding the data relationships, reviewing generated datasets, checking validation results, testing different scenarios, reviewing risk-evaluation outputs, and checking the dashboard.

When I encountered an issue, I looked at the error or unexpected output and worked through the correction with ChatGPT. I also checked whether the changes produced the expected results.

## Where ChatGPT Helped

ChatGPT helped me work more efficiently in several areas:


- Exploring approaches for generating connected industrial datasets.
- improving parts of the Python implementation.
- Understanding validation rules and handling incorrect data.
- Working through maintenance records and downtime calculations.
- Developing the risk-scoring and historical evaluation logic.
- Debugging issues and reviewing project outputs.
-checking the final documentation.



## Testing and Verification

I ran the project in my local environment and reviewed the results. The recorded verification included:

- Generating the baseline datasets and checking their record counts.
- Checking that baseline data validation reported zero errors.
- Testing five deliberately created exception scenarios.
- Reviewing maintenance relationships and timestamp calculations.
- Checking 450 maintenance status-history records.
- Running the automated tests, with 12 tests passing.
- Reviewing the historical risk-evaluation results.
- Comparing two independent pipeline runs using row counts and SHA-256 checksums across 24 CSV files.
- Checking JSON and SQLite export counts and SQLite foreign-key integrity.
- Running and reviewing the Streamlit dashboard.

## My Takeaway

This project helped me put my programming and data-handling knowledge into practice on a larger problem. I also learned how to approach unfamiliar technical areas, evaluate suggested solutions, and use AI effectively as part of a development workflow.

ChatGPT helped me save time, explore better solutions, and overcome implementation challenges. I remained involved in the project decisions, local execution, review, and testing, and I take responsibility for understanding the solution I submitted.

## Technical Limitations

- All operational records are synthetic.
- The risk engine is rule-based; its scores are not calibrated failure probabilities.
- The held-out evaluation shows limited recall.
- Downtime is a synthetic estimate based on failure and maintenance completion timestamps.
- The SQL seed file was generated, but replaying it into a fresh database has not yet been verified.
- The project has not been tested using real industrial plant data.
