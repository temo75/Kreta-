import requests, json
u="https://www.fuel-prices.eu/live/api.php"
for lat,lng in [(35.3656,24.4820),(35.3387,25.1442),(35.5138,24.0180),(35.19,25.715)]:
 r=requests.get(u,params={"action":"stations","country":"GR","lat":lat,"lng":lng,"radius":50,"limit":100},timeout=30)
 print("HTTP",r.status_code,"URL",r.url)
 print(r.text[:2500])
