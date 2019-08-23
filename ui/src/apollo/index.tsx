/*
 * Apollo client for HTTP requests
 *
 */
import ApolloClient from "apollo-boost";

let uri;
let local_host = "localhost";


if (document.location.hostname==local_host && false){
	uri = "http://localhost:8888/graphql"
} else {
	uri = "http://api.digitalpoints.io/graphql"
}


export default new ApolloClient({
	uri: uri
});