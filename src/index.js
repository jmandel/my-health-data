import "babel-polyfill"
import smart, {
  matchTags
} from "./smart.js"
import epicEndpointsJson from './epic.json'

const redirectUri = window.location.href.replace('index.html', 'redirect.html')

const sandboxEndpoints = [{
  fhirBaseUrl: 'http://launch.smarthealthit.org/v/r2/sim/eyJoIjoiMSJ9/fhir',
  name: 'SMART Sandbox R2',
  tags: ['sandbox', 'smart']
}, {
  fhirBaseUrl: 'https://open-ic.epic.com/argonaut/api/FHIR/Argonaut/',
  name: 'Epic Argonaut Sandbox',
  tags: ['sandbox', 'epic']
}]

const productionEndpoints = epicEndpointsJson
  .Entries.map(e => ({
    fhirBaseUrl: e.FHIRPatientFacingURI,
    name: e.OrganizationName,
    tags: ['production', 'epic']
  }))

const endpoints = sandboxEndpoints.concat(productionEndpoints)

const getRegistration = (endpoint) => ({
  redirect_uri: redirectUri,
  client_id: matchTags(endpoint.tags, [
    [tags => tags.includes('smart') && tags.includes('sandbox'), 'default_client_id'],
    [tags => tags.includes('epic') && tags.includes('sandbox'), '28291f68-4785-4caa-afff-b10db07d3012'],
    [tags => tags.includes('epic') && tags.includes('production'), 'b916be73-b018-48ff-9926-1494b8dfba5e'],
  ])
})

async function makeClient(fhirBaseUrl, steps = ['oauthUris', 'authorize', 'token']) {
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

const fhirServerToTest = sandboxEndpoints[0].fhirBaseUrl
makeClient(fhirServerToTest)
  .then(c => {
    console.log("Client State", c)
  })