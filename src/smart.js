import uuid from "uuid";
import queryString from "query-string"

const smartOAuthExtension = 'http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris';

const client = async (endpoint, registrations, fetch = window.fetch) => {
  const clientDetails = registrations[endpoint]
  const metadata = await fetch(
    endpoint + (endpoint.slice(-1) === '/' ? '' : '/') + 'metadata', {
      headers: {
        'Accept': 'application/json+fhir'
      }
    }).then(r => r.json())

  const serverUrls = metadata.rest[0].security
    .extension
    .filter(e => e.url === smartOAuthExtension)[0]
    .extension
    .reduce((ret, v) => ({...ret, [v.url]: v.valueUri}), {})

  return { endpoint, clientDetails, serverUrls, metadata }
}

const authorize = (clientState, fetch = window.fetch) => {
  return new Promise((resolve, reject) => {
    const state = uuid()
    const authorizeRequest = {
      response_type: 'code',
      client_id: clientState.clientDetails.client_id,
      redirect_uri: clientState.clientDetails.redirect_uri,
      scope: 'patient/*.read',
      state,
      aud: clientState.endpoint
    }

    const authorizeLink = clientState.serverUrls.authorize +
      '?' +
      queryString.stringify(authorizeRequest)

    const authorizeWindow = window.open(authorizeLink)
    const channel = new BroadcastChannel(state)
    channel.onmessage = e => resolve({...clientState,
      authorizeRequest,
      authorizeResponse: e.data})
  })
}

const token = async (clientState, fetch = window.fetch) => {
  const tokenUrl = clientState.serverUrls.token
  const tokenRequest = {
    grant_type: 'authorization_code',
    code: clientState.authorizeResponse.code,
    redirect_uri: clientState.clientDetails.redirect_uri,
    client_id: clientState.clientDetails.client_id
  }

  const tokenResponse = await fetch(
    tokenUrl, {
      method: 'POST',
      mode: 'cors',
      body: queryString.stringify(tokenRequest),
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    }).then(r=>r.json())

  return {...clientState, tokenRequest, tokenResponse}
}

export default {
  client, authorize, token
}
