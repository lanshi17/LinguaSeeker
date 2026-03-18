# src/domain/literature/hans_publishers/locators.py
"""XPath locators for Hans Publishers website interaction."""

# Search input and button
XPATH_SEARCH_INPUT = '//*[@id="ctl00_WebUserControl_Seach1_Txtsearch"]'
XPATH_SEARCH_BUTTON = (
    '//*[@id="ctl00_WebUserControl_Seach1_Panel_search"]/div/div/button'
)

# Results container
XPATH_RESULTS_CONTAINER = '//*[@id="aspnetForm"]/div[3]/div/div[2]/div[2]'

# PDF link on article detail page
XPATH_PDF_LINK = '//*[@id="aritsear"]/div[1]/div/p[3]/a[3]'
