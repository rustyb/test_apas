# import the libraries for scraping
import scraperwiki           
from lxml import html
import requests
import re


# Next we will use requests.get to retrieve the web page with our data, parse it using the html module and save the results in tree:
#remove the extra characters using regex
def remove_characters(clump):
    return re.sub(r'[\r\n\t\xa0]+', '', clump)

def scrape_application(link):
    #get data on agent and application person
    details_page = link
    print 'Scraping Details: ', details_page
    page_d = scraperwiki.scrape(details_page)
    tree_app = html.fromstring(page_d)
    
    #get data from decision tab page
    decision_page = link + '&theTabNo=2'
    print 'Scraping Decision: ', decision_page
    page = scraperwiki.scrape(decision_page)
    tree = html.fromstring(page)
   
    data = {
        'info_url' : link,
        'decision' : remove_characters(tree.cssselect("div#tabs_container div#tabContent div#fieldset_data p.fieldset_data")[0].text),
        'app_date' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[0].text_content()),
        'app_ref' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[1].text),
        'reg_date' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[2].text),
        'decision_date' : remove_characters(tree.cssselect("div#tabs_container div#tabContent div#fieldset_data p.fieldset_data")[1].text),
        'app_type' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[4].text),
        'ext_date' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[5].text),
        'main_loc' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[6].text),
        'desc' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[7].text),
        'full_desc' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[8].text),
        'app_status' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[9].text),
        'status_desc' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[10].text),
        'comment' : remove_characters(tree.cssselect("div#apas_form fieldset.apas div#fieldset_data p.fieldset_data")[11].text),
        'application_company' : remove_characters(tree_app.cssselect("div#tabs_container div#tabContent div#fieldset_data p.fieldset_data")[2].text),
        'agent' : remove_characters(tree_app.cssselect("div#tabs_container div#tabContent div#fieldset_data p.fieldset_data")[8].text)
        }
    print 'Scraping Complete :) NEXT! \n\n'
    scraperwiki.sqlite.save(unique_keys=['app_ref'], data=data)



#print data
#this = tree.cssselect("div#tabs_container div#tabContent div#fieldset_data p.fieldset_data")[0].text
#print this
#links = ['http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0260',
#'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0598']


    
    


links = ['http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0260',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0598',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0152/C1',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D13A/0193/C3',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0588',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0590',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D09A/0357/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0286',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0134',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0229',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1165/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0338',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0515',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0501',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=Ref%209814', #doesn't like spaces
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D98A/0886/E2',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D06A/0927/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D03A/0584/E1',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0360',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0180',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0127',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D14A/0113',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D13A/0252',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1028/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D13A/0636',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D13A/0611',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D12A/0484',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D13A/0170',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D06A/1797/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D11A/0603',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D12A/0262',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D12A/0098',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D04A/0618/E1',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D06A/1797/C6',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D03A/0750/E1',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D12A/0150',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D05A/0579/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D06A/0681/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D04A/0994/E1',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D11A/0312',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D11A/0054',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D05A/1324/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D11A/0297',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D05A/1159/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D05A/1614/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D10A/0719',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D10A/0591',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D10A/0570',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D05A/1121/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D04A/0674/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D09A/0908',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D10A/0290',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D09A/0827',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8028',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8029',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8030',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8031',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8032',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8033',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8034',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8035',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8036',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8025',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8026',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8027',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8024',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8022',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=10/8023',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D09A/0534',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D04A/0618/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1408',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D04A/0327/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D03A/0750/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D98A/0886/E1',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1379',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D03A/0584/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1165',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D04A/0994/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=09/8041',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=09/8028',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D03A/0291/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D09A/0162',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0897',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1422',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0457',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1305',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1028',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0843',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1112',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8204',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0414',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0454',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/1004',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8189',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8175',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8142',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8143',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8139',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8140',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8141',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8138',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0717',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8133',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1495',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1269',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0521',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=v/072/08',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8092',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8093',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8094',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8095',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8096',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8097',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8098',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8099',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8100',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0449',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0434',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D02A/1061/E',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1175',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D05A/1390/C4',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8060',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0324',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0300',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D06A/1943',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/0936',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0229',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8047',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8041',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8028',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8029',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D06A/1628',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0070',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D08A/0033',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D06A/1367',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=08/8003',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=07/8293',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1775',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=07/8282',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=07/8277',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1598',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/0984',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1117',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/0608',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1545',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1496',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/0759',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1449',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1450',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1445',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/0798',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=07/8216',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=07/8213',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1351',
'http://planning.dlrcoco.ie/swiftlg/apas/run/WPHAPPDETAIL.DisplayUrl?theApnID=D07A/1353']

for link in links:
    scrape_application(link)
