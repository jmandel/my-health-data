import "babel-polyfill";
import smart from "./smart.js";

const versionToTest = 'r2';
const endpointTemplate = 'http://launch.smarthealthit.org/v/:version:/sim/eyJoIjoiMSJ9/fhir'

const registrations = {
    [endpointTemplate.replace(':version:', 'r2')] : {
      'client_id': 'default_client_id',
      'redirect_uri': window.location.href.replace('index.html', 'redirect.html')
    },
    [endpointTemplate.replace(':version:', 'r3')] : {
      'client_id': 'default_client_id',
      'redirect_uri': window.location.href.replace('index.html', 'redirect.html')
    },
    [endpointTemplate.replace(':version:', 'r4')] : {
      'client_id': 'default_client_id',
      'redirect_uri': window.location.href.replace('index.html', 'redirect.html')
    }
  }

async function getClientState(endpoint){

  let clientState = await smart.client(endpoint, registrations)
  clientState = await smart.authorize(clientState)
  clientState = await smart.token(clientState)
  return clientState

}

getClientState(endpointTemplate.replace(':version:', versionToTest)).then(c=> {
  console.log("Client State", c)
})
