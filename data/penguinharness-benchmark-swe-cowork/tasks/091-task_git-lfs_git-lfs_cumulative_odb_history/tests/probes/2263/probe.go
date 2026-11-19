package git

import "testing"

func TestTaskContractRevListOrder(t *testing.T) {
	cases := []struct {
		order   RevListOrder
		flag    string
		enabled bool
	}{
		{RevListOrder(99), "", false}, {DefaultRevListOrder, "", false}, {DateRevListOrder, "--date-order", true},
		{AuthorDateRevListOrder, "--author-date-order", true}, {TopoRevListOrder, "--topo-order", true},
	}
	for _, tc := range cases {
		flag, enabled := tc.order.Flag()
		if flag != tc.flag || enabled != tc.enabled {
			t.Fatalf("order %d => %q,%v", tc.order, flag, enabled)
		}
	}
}
