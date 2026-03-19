# src/domain/literature/pubscholar/locators.py
"""XPath locators for PubScholar website interaction."""

# Search input and button
XPATH_SEARCH_INPUT = '//*[@id="app"]/div[2]/div[1]/div[1]/div/main/section[1]/div/div[2]/div/div[2]/span/span/div/div[1]/div[1]/input'
XPATH_SEARCH_BUTTON = (
    '//*[@id="app"]/div[2]/div[1]/div[1]/div/main/section[1]/div/div[2]/div/button'
)

# Filter headers
XPATH_LANGUAGE_HEADER = '//*[@id="base-collapse-head-9639"]/span'
XPATH_PAPER_TYPE_HEADER = '//*[@id="base-collapse-head-1513"]/span'

# Full text filter button
XPATH_FULLTEXT_BTN = '//*[@id="app"]/div[2]/div/div[1]/div/main/div/div[2]/div/div[2]/div[1]/div[3]/div[1]/div/span[2]/span'

# Results container
XPATH_RESULTS_CONTAINER = (
    '//*[@id="app"]/div[2]/div/div[1]/div/main/div/div[2]/div/div[2]/div[3]'
)

# First journal link (for reference)
XPATH_FIRST_JOURNAL_LINK = '//*[@id="app"]/div[2]/div/div[1]/div/main/div/div[2]/div/div[2]/div[3]/div[1]/div[2]/div/div[5]/div/span[2]'
