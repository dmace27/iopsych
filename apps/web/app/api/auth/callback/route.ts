/** Auth0 callback; authorization codes never reach client-side components. */
export { completeLogin as GET } from "../../../../lib/provider-auth";
