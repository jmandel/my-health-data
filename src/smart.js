import uuid from "uuid";
import queryString from "query-string"

const smartOAuthExtension = 'http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris';

const oauthUris = async (clientState, fetch = window.fetch) => {
  const {
    endpoint,
    registration
  } = clientState

  const fhirBaseUrl = endpoint.fhirBaseUrl + (
    endpoint.fhirBaseUrl.slice(-1) === '/' ? '' : '/'
  )

  const metadataResponse = await fetch(
    fhirBaseUrl + 'metadata', {
      headers: {
        'Accept': 'application/json+fhir'
      }
    }).then(r => r.json())

  const oauthUris = metadataResponse.rest[0].security
    .extension
    .filter(e => e.url === smartOAuthExtension)[0]
    .extension
    .reduce((ret, v) => ({
      ...ret,
      [v.url]: v.valueUri
    }), {})

  return {
    ...clientState,
    oauthUris,
    metadataRaw: metadataResponse
  }
}

const authorize = (clientState, fetch = window.fetch) => {
  return new Promise((resolve, reject) => {
    const state = uuid()
    const authorizeRequest = {
      response_type: 'code',
      client_id: clientState.registration.client_id,
      redirect_uri: clientState.registration.redirect_uri,
      scope: 'patient/*.read',
      state,
      aud: clientState.endpoint.fhirBaseUrl
    }

    const authorizeLink = clientState.oauthUris.authorize +
      '?' +
      queryString.stringify(authorizeRequest)
    const authorizeWindow = window.open(authorizeLink)
    const channel = new BroadcastChannel(state)
    channel.onmessage = e => resolve({
      ...clientState,
      authorizeRequest,
      authorizeResponse: e.data
    })
  })
}

const token = async (clientState, fetch = window.fetch) => {
  const tokenUrl = clientState.oauthUris.token
  const tokenRequest = {
    grant_type: 'authorization_code',
    code: clientState.authorizeResponse.code,
    redirect_uri: clientState.registration.redirect_uri,
    client_id: clientState.registration.client_id
  }

  const tokenResponse = await fetch(tokenUrl, {
    method: 'POST',
    mode: 'cors',
    body: queryString.stringify(tokenRequest),
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  }).then(r => r.json())

  return {
    ...clientState,
    tokenRequest,
    tokenResponse
  }
}

export const matchTags = (tags, matchers) => matchers
  .map(([matchFn, value]) => matchFn(tags) ? value : null)
  .filter(x => x !== null)[0]

export default {
  oauthUris,
  authorize,
  token
}