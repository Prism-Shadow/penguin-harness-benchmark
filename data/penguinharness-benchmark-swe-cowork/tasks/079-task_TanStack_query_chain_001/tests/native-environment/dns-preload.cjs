const dns = require('node:dns')
const originalLookup = dns.lookup

dns.lookup = function lookup(hostname, options, callback) {
  if (hostname === 'localhost') {
    if (typeof options === 'function') return options(null, '127.0.0.1', 4)
    if (typeof callback === 'function') {
      if (options && options.all) return callback(null, [{ address: '127.0.0.1', family: 4 }])
      return callback(null, '127.0.0.1', 4)
    }
  }
  return originalLookup.call(this, hostname, options, callback)
}

dns.promises.lookup = async function lookup(hostname, options) {
  if (hostname === 'localhost') {
    if (options && options.all) return [{ address: '127.0.0.1', family: 4 }]
    return { address: '127.0.0.1', family: 4 }
  }
  return originalLookup.call(dns, hostname, options)
}
