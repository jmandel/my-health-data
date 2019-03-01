import "babel-polyfill"
import smart, {
  matchTags
} from "./smart.js"

import endpoints from "./endpoints.js"

const redirectUri = window.location.href
  .replace('index.html', 'redirect.html')
  .replace(/#.*/, '')

const getRegistration = (endpoint) => ({
  redirect_uri: "https://joshuamandel.com/my-health-data/redirect.html",
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

makeClient(fhirServerToTest).then(console.log)