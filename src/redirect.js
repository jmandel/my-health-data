import "babel-polyfill";
import queryString from "query-string"

const results = queryString.parse(window.location.search)
new BroadcastChannel(results.state).postMessage(results)

window.close()
