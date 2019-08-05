# my-health-data

I'm creating this SMART on FHIR App for my own personal use; it's designed to help me retrieve my own data in FHIR.

No one other than me (Josh Mandel) should share their records with it.

## Dev

* https://parceljs.org/getting_started.html
* `curl -s https://open.epic.com/MyApps/EndpointsJson > src/epic.json`
* add `$(yarn global bin)` to `PATH`
* `yarn install`
* `parcel src/*.html`
* browse to http://localhost:1234/index.html
parcel build src/*.html  --public-url https://joshuamandel.com/my-health-data/
