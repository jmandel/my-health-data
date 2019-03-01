import epicEndpointsJson from './epic.json'

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
export default endpoints