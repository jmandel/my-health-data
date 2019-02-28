import "babel-polyfill"
import smart from "./smart.js"
import epicEndpointsJson from './epic.json'

const versionToTest = 'r2'
const endpointTemplate = 'http://launch.smarthealthit.org/v/:version:/sim/eyJoIjoiMSJ9/fhir'
const redirectUri = window.location.href.replace('index.html', 'redirect.html')

const sandboxRegistrations = {
  [endpointTemplate.replace(':version:', 'r2')]: {
    'client_id': 'default_client_id',
    'redirect_uri': redirectUri
  },
  [endpointTemplate.replace(':version:', 'r3')]: {
    'client_id': 'default_client_id',
    'redirect_uri': redirectUri
  },
  [endpointTemplate.replace(':version:', 'r4')]: {
    'client_id': 'default_client_id',
    'redirect_uri': redirectUri
  },
  'https://open-ic.epic.com/argonaut/api/FHIR/Argonaut/': {
    'client_id': '28291f68-4785-4caa-afff-b10db07d3012',
    'redirect_uri': redirectUri
  }
}

const registrations = epicEndpointsJson
  .Entries.map(e => ({
    name: e.OrganizationName,
    endpoint: e.FHIRPatientFacingURI,
    client_id: 'b916be73-b018-48ff-9926-1494b8dfba5e',
    redirect_uri: redirectUri,
  }))
  .reduce((ret, e) => ({
    ...ret,
    [e.endpoint]: e
  }), sandboxRegistrations)

async function getClientState(endpoint) {
  let clientState
  clientState = await smart.client(endpoint, registrations)
  clientState = await smart.authorize(clientState)
  clientState = await smart.token(clientState)
  return clientState
}

getClientState(endpointTemplate.replace(':version:', versionToTest))
  .then(c => {
    console.log("Client State", c)
  })