package blockchain

import (
	"errors"
	"testing"
	"time"

	"github.com/btcsuite/btcd/chaincfg"
	"github.com/btcsuite/btcd/chaincfg/chainhash"
	"github.com/btcsuite/btcd/wire"
)

type segpipe2467ChainCtx struct {
	params *chaincfg.Params
}

func (c segpipe2467ChainCtx) ChainParams() *chaincfg.Params {
	return c.params
}

func (c segpipe2467ChainCtx) BlocksPerRetarget() int32 {
	return int32(c.params.TargetTimespan / c.params.TargetTimePerBlock)
}

func (c segpipe2467ChainCtx) MinRetargetTimespan() int64 {
	return int64(c.params.TargetTimespan /
		time.Duration(c.params.RetargetAdjustmentFactor))
}

func (c segpipe2467ChainCtx) MaxRetargetTimespan() int64 {
	return int64(c.params.TargetTimespan *
		time.Duration(c.params.RetargetAdjustmentFactor))
}

func (segpipe2467ChainCtx) VerifyCheckpoint(int32, *chainhash.Hash) bool {
	return true
}

func (segpipe2467ChainCtx) FindPreviousCheckpoint() (HeaderCtx, error) {
	return nil, nil
}

func TestSegpipe2467RegtestEnforcesBuriedBlockVersions(t *testing.T) {
	params := chaincfg.RegressionNetParams
	previous := newBlockNode(&params.GenesisBlock.Header, nil)
	header := &wire.BlockHeader{
		Version:   1,
		PrevBlock: *params.GenesisHash,
		Bits:      params.PowLimitBits,
		Timestamp: time.Unix(previous.Timestamp()+1, 0),
	}

	err := CheckBlockHeaderContext(
		header, previous, BFFastAdd,
		segpipe2467ChainCtx{params: &params}, true,
	)
	var ruleErr RuleError
	if !errors.As(err, &ruleErr) || ruleErr.ErrorCode != ErrBlockVersionTooOld {
		t.Fatalf("regtest version-1 header error=%v, want ErrBlockVersionTooOld", err)
	}
}

type segpipe2467HeaderContext struct { height int32 }
func (c segpipe2467HeaderContext) Height() int32 {return c.height}
func (segpipe2467HeaderContext) Bits() uint32 {return 0x207fffff}
func (segpipe2467HeaderContext) Timestamp() int64 {return 1}
func (segpipe2467HeaderContext) Parent() HeaderCtx {return nil}
func (segpipe2467HeaderContext) RelativeAncestorCtx(int32) HeaderCtx {return nil}

func TestSegpipe2467ConfiguredVersionActivation(t *testing.T) {
 params:=chaincfg.RegressionNetParams
 params.BIP0034Height=10;params.BIP0066Height=20;params.BIP0065Height=30
 for _,test:=range []struct{height,version int32;reject bool}{
  {9,1,false},{10,1,true},{10,2,false},{19,2,false},{20,2,true},{20,3,false},{29,3,false},{30,3,true},{30,4,false},
 } {
  header:=&wire.BlockHeader{Version:test.version}
  err:=CheckBlockHeaderContext(header,segpipe2467HeaderContext{test.height-1},BFFastAdd,segpipe2467ChainCtx{params:&params},true)
  if test.reject {var rule RuleError;if !errors.As(err,&rule)||rule.ErrorCode!=ErrBlockVersionTooOld {t.Fatalf("height %d version %d: %v",test.height,test.version,err)}} else if err!=nil {t.Fatalf("valid height %d version %d: %v",test.height,test.version,err)}
 }
}
