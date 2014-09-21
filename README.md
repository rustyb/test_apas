This is a scraper that runs on [Morph](https://morph.io). To get started [see the documentation](https://morph.io/documentation)

### DLRCOCO Planning Application Details Scraper
To use this scraper you must first provide the scraper with a list of planning application urls to the [DLRcoco](http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.Display) APAS system.

The urls should take the form of:
    http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0501

Where **D14A/0501** is the registered reference for the planning application.

This Scraper will out put the scraped info as follows to a sqllite database:

info_url : Url to the application file
decision : Application Decision
app_date : 
app_ref : 
reg_date : 
decision_date : 
app_type : 
ext_date : 
main_loc : 
desc : 
full_desc : 
app_status : 
status_desc : 
comment : 
application_company : 
agent :
