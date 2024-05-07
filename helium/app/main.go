package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"time"

	"github.com/ChristianMct/helium"
	"github.com/ChristianMct/helium/circuits"
	"github.com/ChristianMct/helium/objectstore"
	"github.com/ChristianMct/helium/protocols"
	"github.com/ChristianMct/helium/services/compute"
	"github.com/ChristianMct/helium/services/setup"
	"github.com/ChristianMct/helium/sessions"
	"github.com/tuneinsight/lattigo/v5/core/rlwe"
	"github.com/tuneinsight/lattigo/v5/he"
	"github.com/tuneinsight/lattigo/v5/mhe"
	"github.com/tuneinsight/lattigo/v5/schemes/bgv"
	"golang.org/x/exp/maps"
	"gonum.org/v1/gonum/mat"

	"github.com/ChristianMct/helium/node"
)

const DefaultAddress = ":40000"

var (
	nodeId       = flag.String("node_id", "", "the id of the node")
	nParty       = flag.Int("n_party", -1, "the number of parties")
	cloudAddr    = flag.String("cloud_address", "", "the address of the helper node")
	argThreshold = flag.Int("threshold", -1, "the threshold")
	//expDuration  = flag.Duration("expDuration", 0, "the duration of the experiment, see time.ParseDuration for valid input formats.")
	expRounds = flag.Int("expRounds", 1, "number of circuit evaluatation rounds to perform")
)

func genNodeLists(nParty int, cloudAddr string) (nids []sessions.NodeID, nl node.List, shamirPks map[sessions.NodeID]mhe.ShamirPublicPoint, nodeMapping map[string]sessions.NodeID) {
	nids = make([]sessions.NodeID, nParty)
	nl = make(node.List, nParty)
	shamirPks = make(map[sessions.NodeID]mhe.ShamirPublicPoint, nParty)
	nodeMapping = make(map[string]sessions.NodeID, nParty+2)
	nodeMapping["cloud"] = "cloud"
	for i := range nids {
		nids[i] = sessions.NodeID(fmt.Sprintf("node-%d", i))
		nl[i].NodeID = nids[i]
		shamirPks[nids[i]] = mhe.ShamirPublicPoint(i + 1)
		nodeMapping[string(nids[i])] = nids[i]
	}
	nl = append(nl, struct {
		sessions.NodeID
		node.Address
	}{NodeID: "cloud", Address: node.Address(cloudAddr)})
	return
}

func genNodeConfigForNode(nid sessions.NodeID, nids []sessions.NodeID, threshold int, shamirPks map[sessions.NodeID]mhe.ShamirPublicPoint) (nc node.Config) {
	sessParams := sessions.Parameters{
		ID:            "test-session",
		Nodes:         nids,
		FHEParameters: bgv.ParametersLiteral{PlaintextModulus: 79873, LogN: 12, LogQ: []int{45, 45}, LogP: []int{19}},
		Threshold:     threshold,
		PublicSeed:    []byte{'c', 'r', 's'},
		ShamirPks:     shamirPks,
	}

	nc = node.Config{
		ID:                nid,
		HelperID:          "cloud",
		SessionParameters: []sessions.Parameters{sessParams},
		ObjectStoreConfig: objectstore.Config{BackendName: "mem"},
		TLSConfig:         node.TLSConfig{InsecureChannels: true},
		SetupConfig: setup.ServiceConfig{
			Protocols: protocols.ExecutorConfig{MaxProtoPerNode: 3, MaxParticipation: 1, MaxAggregation: 1},
		},
		ComputeConfig: compute.ServiceConfig{
			MaxCircuitEvaluation: 10,
			Protocols:            protocols.ExecutorConfig{MaxProtoPerNode: 3, MaxParticipation: 1, MaxAggregation: 1},
		},
	}

	if nid == "cloud" {
		nc.Address = DefaultAddress
		nc.SetupConfig.Protocols.MaxAggregation = 32
		nc.ComputeConfig.Protocols.MaxAggregation = 32
	} else {
		var err error
		nc.SessionParameters[0].Secrets, err = loadSecrets(sessParams, nid)
		if err != nil {
			log.Fatalf("could not load node's secrets: %s", err)
		}
	}
	return
}

func getApp(params bgv.Parameters, m int) node.App {
	diagGalEl := make(map[int]uint64)
	for k := 0; k < m; k++ {
		diagGalEl[k] = params.GaloisElement(k)
	}
	return node.App{
		SetupDescription: &setup.Description{
			Cpk: true,
			Rlk: true,
			Gks: maps.Values(diagGalEl),
		},
		Circuits: map[circuits.Name]circuits.Circuit{
			"matmul4-dec": matmul4dec,
		},
	}
}

func getInputProvider(params bgv.Parameters, encoder *bgv.Encoder, m int) compute.InputProvider {
	return func(ctx context.Context, ci sessions.CircuitID, ol circuits.OperandLabel, s sessions.Session) (any, error) {

		encoder := encoder.ShallowCopy()

		var pt *rlwe.Plaintext
		b := mat.NewVecDense(m, nil)
		b.SetVec(0, 1)
		data := make([]uint64, len(b.RawVector().Data))
		for i, bi := range b.RawVector().Data {
			data[i] = uint64(bi)
		}

		pt = bgv.NewPlaintext(params, params.MaxLevelQ())
		err := encoder.Encode(data, pt)

		if err != nil {
			return nil, err
		}

		return pt, nil

	}
}

func checkResultCorrect(params bgv.Parameters, encoder bgv.Encoder, out circuits.Output, a *mat.Dense) error {
	_, m := a.Dims()

	b := mat.NewVecDense(m, nil)
	b.SetVec(0, 1)
	r := mat.NewVecDense(m, nil)

	r.MulVec(a, b)
	dataWant := make([]uint64, len(r.RawVector().Data))
	for i, v := range r.RawVector().Data {
		dataWant[i] = uint64(v)
	}

	pt := &rlwe.Plaintext{Element: out.Ciphertext.Element, Value: out.Ciphertext.Value[0]}
	pt.IsBatched = true
	res := make([]uint64, params.MaxSlots())
	if err := encoder.Decode(pt, res); err != nil {
		return fmt.Errorf("error decoding result: %v", err)
	}
	res = res[:m]

	for i, v := range res {
		if v != dataWant[i] {
			//panic(fmt.Errorf("incorrect result for %s: \n has %v, want %v", opl, res, dataWant))
			return fmt.Errorf("incorrect result for %s: \n has %v, want %v\n", out.OperandLabel, res, dataWant)
		}
	}
	return nil
}

func getTestMatrix(m int) *mat.Dense {
	a := mat.NewDense(m, m, nil)
	a.Apply(func(i, j int, v float64) float64 {
		return float64(i) + float64(2*j)
	}, a)
	return a
}

// main is the entrypoint of the node application.
// Instructions to run: go run main.go node.go -config [nodeconfigfile].
func main() {

	flag.Parse()

	if *nParty < 2 {
		panic("n_party argument should be provided and > 2")
	}

	if len(*nodeId) == 0 {
		panic("node_id argument should be provided")
	}

	if len(*cloudAddr) == 0 {
		panic("cloud_address argument must be provided for session nodes")
	}

	var threshold int
	switch {
	case *argThreshold == -1:
		threshold = *nParty
	case *argThreshold > 0 && *argThreshold <= *nParty:
		threshold = *argThreshold
	default:
		flag.Usage()
		panic("threshold argument must be between 1 and N")
	}

	nid := sessions.NodeID(*nodeId)

	nids, nl, shamirPks, nodeMapping := genNodeLists(*nParty, *cloudAddr)

	nc := genNodeConfigForNode(nid, nids, threshold, shamirPks)

	params, err := bgv.NewParametersFromLiteral(nc.SessionParameters[0].FHEParameters.(bgv.ParametersLiteral))
	if err != nil {
		panic(err)
	}
	m := params.MaxSlots() / 2
	app := getApp(params, m)
	a := getTestMatrix(m)
	encoder := bgv.NewEncoder(params) // TODO pass encoder in ip ?

	var start time.Time
	var ip compute.InputProvider = getInputProvider(params, encoder, m)

	sessId := sessions.ID("test-session")
	ctx := sessions.NewBackgroundContext(sessId)

	start = time.Now()
	var timeSetup, timeCompute time.Duration
	var stats map[string]interface{}

	var nSig int
	if nc.ID == "cloud" {

		hsv, cdescs, outs, err := helium.RunHeliumServer(ctx, nc, nl, app, compute.NoInput)
		if err != nil {
			log.Fatalf("error running helium server: %v", err)
		}

		timeSetup = time.Since(start)

		if err := encryptTestMatrix(ctx, a, params, encoder, hsv, hsv); err != nil {
			log.Fatalf("error encrypting test matrix: %v", err)
		}

		go func() {
			for i := 0; i < *expRounds; i++ {
				cdescs <- circuits.Descriptor{
					Signature:   circuits.Signature{Name: "matmul4-dec"},
					CircuitID:   sessions.CircuitID(fmt.Sprintf("matmul-%d", nSig)),
					NodeMapping: nodeMapping,
					Evaluator:   "cloud",
				}
				nSig++
			}
			close(cdescs)
		}()

		out, has := <-outs
		if has {
			log.Fatalf("unexpected output: %v", out.OperandLabel)
		}

		hsv.GracefulStop() // waits for the last client to disconnect

		timeCompute = time.Since(start) - timeSetup

		stats = map[string]interface{}{
			"Time": map[string]interface{}{
				"Setup":   timeSetup,
				"Compute": timeCompute,
			},
			"Net": hsv.GetStats(),
		}
	} else {
		hc, outs, err := helium.RunHeliumClient(ctx, nc, nl, app, ip)
		if err != nil {
			log.Fatalf("error running helium client: %v", err)
		}

		for out := range outs {
			if err = checkResultCorrect(params, *encoder, out, a); err != nil {
				log.Printf("error checking result: %v", err)
			} else {
				log.Printf("got correct result for %s", out.OperandLabel)
			}
		}

		if err := hc.Close(); err != nil {
			log.Fatalf("error closing helium client: %v", err)
		}

		stats = map[string]interface{}{
			"net": hc.GetStats(),
		}
	}

	statsJson, err := json.Marshal(stats)
	if err != nil {
		log.Fatalf("error marshalling stats: %v", err)
	}
	fmt.Println("STATS", string(statsJson))
}

func encryptTestMatrix(ctx context.Context, a *mat.Dense, params bgv.Parameters, encoder *bgv.Encoder, pkb circuits.PublicKeyProvider, opp compute.OperandProvider) error {

	cpk, err := pkb.GetCollectivePublicKey(ctx)
	if err != nil {
		return err
	}
	encryptor := bgv.NewEncryptor(params, cpk)

	pta := make(map[int]*rlwe.Plaintext)
	cta := make(map[int]*rlwe.Ciphertext)

	_, m := a.Dims()
	diag := make(map[int][]uint64, m)
	for k := 0; k < m; k++ {
		diag[k] = make([]uint64, m)
		for i := 0; i < m; i++ {
			j := (i + k) % m
			diag[k][i] = uint64(a.At(i, j))
		}
	}

	log.Printf("generating encrypted matrix...")
	for di, d := range diag {
		pta[di] = bgv.NewPlaintext(params, params.MaxLevelQ())
		if err = encoder.Encode(d, pta[di]); err != nil {
			return err
		}
		if cta[di], err = encryptor.EncryptNew(pta[di]); err != nil {
			return err
		}
		op := &circuits.Operand{Ciphertext: cta[di], OperandLabel: circuits.OperandLabel(fmt.Sprintf("//cloud/mat-diag-%d", di))}
		if err := opp.PutOperand(op.OperandLabel, op); err != nil {
			return err
		}
	}
	log.Printf("done")
	return nil
}

func matmul4dec(e circuits.Runtime) error {
	params := e.Parameters().(bgv.Parameters)

	m := params.MaxSlots() / 2

	vecOp := e.Input(circuits.OperandLabel("//node-0/vec"))

	matOps := make(map[int]*circuits.Operand)
	diagGalEl := make(map[int]uint64)
	for k := 0; k < m; k++ {
		matOps[k] = e.Load(circuits.OperandLabel(fmt.Sprintf("//cloud/mat-diag-%d", k)))
		diagGalEl[k] = params.GaloisElement(k)
	}

	opRes := e.NewOperand("//cloud/res-0")
	if err := e.EvalLocal(true, maps.Values(diagGalEl), func(e he.Evaluator) error {
		opRes.Ciphertext = bgv.NewCiphertext(params, 1, params.MaxLevel())

		eval, isBgv := e.(*bgv.Evaluator)
		if !isBgv {
			return fmt.Errorf("evaluator is not a *bgv.Evaluator, is %T", e)
		}
		eval.DecomposeNTT(params.MaxLevelQ(), params.MaxLevelP(), params.PCount(), vecOp.Get().Value[1], true, eval.BuffDecompQP)
		vecRotated := bgv.NewCiphertext(params, 1, params.MaxLevelQ())
		ctprod := bgv.NewCiphertext(params, 2, params.MaxLevel())
		for di, d := range matOps {
			if err := eval.AutomorphismHoisted(vecOp.LevelQ(), vecOp.Ciphertext, eval.BuffDecompQP, diagGalEl[di], vecRotated); err != nil {
				return err
			}
			if err := e.MulThenAdd(vecRotated, d.Ciphertext, ctprod); err != nil {
				return err
			}
		}
		return e.Relinearize(ctprod, opRes.Ciphertext)
	}); err != nil {
		return err
	}

	return e.DEC(*opRes, "node-0", map[string]string{
		"smudging": "40.0",
	})
}

// simulates loading the secrets. In a real application, the secrets would be loaded from a secure storage.
func loadSecrets(sp sessions.Parameters, nid sessions.NodeID) (secrets *sessions.Secrets, err error) {

	ss, err := sessions.GenTestSecretKeys(sp)
	if err != nil {
		return nil, err
	}

	secrets, ok := ss[nid]
	if !ok {
		return nil, fmt.Errorf("node %s not in session", nid)
	}

	return
}
