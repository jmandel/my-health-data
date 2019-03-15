import "babel-polyfill"
import smart, {
  matchTags
} from "./smart.js"

import endpoints from "./endpoints.js"

const redirectUri = window.location.href
  .replace('index.html', 'redirect.html')
  .replace(/#.*/, '')

const getRegistration = (endpoint) => ({
  redirect_uri: redirectUri, // "https://joshuamandel.com/my-health-data/redirect.html",
  client_id: matchTags(endpoint.tags, [
    [tags => tags.includes('smart') && tags.includes('sandbox'), 'default_client_id'],
    [tags => tags.includes('epic') && tags.includes('sandbox'), 'c09dc775-96b6-4fd0-828a-5c2daf481ff1'],
    [tags => tags.includes('epic') && tags.includes('production'), 'b916be73-b018-48ff-9926-1494b8dfba5e'],
  ])
})

async function makeClient(fhirBaseUrl, steps = ['oauth', 'authorize', 'token']) {
  let endpoint = endpoints.filter(r => r.fhirBaseUrl === fhirBaseUrl)[0]
  let registration = getRegistration(endpoint)

  let clientState = {
    endpoint,
    registration
  }
  for (let step of steps) {
    clientState = await smart[step](clientState)
  }
  return clientState
}

// Eventually we'll have a UI
let serverPick = window.location.hash.slice(1) || 'smart'
let fhirServerToTest = {
  smart: endpoints[0].fhirBaseUrl,
  epic: endpoints[1].fhirBaseUrl,
  unity: 'https://epicfhir.unitypoint.org/ProdFHIR/api/FHIR/DSTU2/',
  uw: 'https://epicproxy.hosp.wisc.edu/FhirProxy/api/FHIR/DSTU2/'
} [serverPick]

makeClient(fhirServerToTest).then(c => {
  console.log(c)

  console.log(`
  export TOKEN=${c.tokenResponse.access_token}
  export PATIENT=${c.tokenResponse.patient}
  export ENDPOINT=${c.endpoint.fhirBaseUrl}
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/Patient/$PATIENT" > patient.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/Observation?category=social-history&patient=$PATIENT" > social-history.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/Observation?category=laboratory&patient=$PATIENT" > laboratory.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/Observation?category=vital-signs&patient=$PATIENT" > vital-signs.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/Condition?patient=$PATIENT" > condition.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/MedicationOrder?patient=$PATIENT" > medication-order.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/MedicationStatement?patient=$PATIENT" > medication-statement.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/AllergyIntolerance?patient=$PATIENT" > allergy-intolerance.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/Procedure?patient=$PATIENT" > procedure.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/Immunization?patient=$PATIENT" > immunization.json
  curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$ENDPOINT/DocumentReference?patient=$PATIENT" > document-reference.json

  for dr in $(cat document-reference.json  | jq '.entry[].resource | select(.resourceType == "DocumentReference") | .content[0].attachment.url' -r)
  do
    echo $dr;
    curl -H 'Accept: application/json' -H "Authorization: BEARER $TOKEN" "$dr" > document-reference-$(echo $dr | awk -F/ '{print $(NF)}').xml
  done
  `)
})
