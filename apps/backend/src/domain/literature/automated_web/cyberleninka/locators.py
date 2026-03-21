# src/domain/literature/cyberleninka/locators.py
"""XPath locators for CyberLeninka website interaction."""

# Search input and button
XPATH_SEARCH_INPUT = '//*[@id="search-box-light"]/form/fieldset/input'
XPATH_SEARCH_BUTTON = '//*[@id="search-box-light"]/form/fieldset/button'

# Subject filter
XPATH_SUBJECT_FILTER = '//*[@id="body"]/div[3]/div/div[1]/div[2]/div/div[2]/div'
XPATH_SUBJECT_LIST = '//*[@id="body"]/div[3]/div/div[1]/div[2]/div/div[2]/ul'

# Results container
XPATH_RESULTS = '//*[@id="search-results"]'
XPATH_FIRST_TITLE = '//*[@id="search-results"]/li[1]/h2'

# Download button on article detail page
XPATH_DOWNLOAD_BTN = '//*[@id="btn-download"]'
