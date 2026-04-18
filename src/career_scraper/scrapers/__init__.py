from .microsoft import MicrosoftScraper
from .google import GoogleScraper
from .amazon import AmazonScraper
from .apple import AppleScraper
from .meta import MetaScraper
from .sap import SAPScraper
from .oracle import OracleScraper
from .visa import VisaScraper
from .salesforce import SalesforceScraper

SCRAPERS = {
    "microsoft": MicrosoftScraper,
    "google": GoogleScraper,
    "amazon": AmazonScraper,
    "apple": AppleScraper,
    "meta": MetaScraper,
    "sap": SAPScraper,
    "oracle": OracleScraper,
    "visa": VisaScraper,
    "salesforce": SalesforceScraper,
}
