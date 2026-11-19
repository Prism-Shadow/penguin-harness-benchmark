package addrmgr
import("net";"testing";"time";"github.com/btcsuite/btcd/wire")
func TestSegpipe2479ORCHIDv2Routing(t *testing.T) {
 for _,tc:=range []struct{ip string;want bool}{
 {"2001:20::1",false},{"2001:2f:ffff::1",false},{"2001:4860:4860::8888",true},
 } {na:=wire.NetAddressV2FromBytes(time.Unix(1,0),wire.SFNodeNetwork,net.ParseIP(tc.ip),8333)
 if got:=IsRoutable(na);got!=tc.want {t.Fatalf("%s routable=%v want %v",tc.ip,got,tc.want)}}
}
