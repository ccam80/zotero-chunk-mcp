# active-inference-tutorial — Ground Truth Review

Paper: Active Inference Tutorial
Item key: SCPXVBLY
Total tables: 8 (1 artifact + 7 data)

---

## table_0 (p1) — ARTIFACT

- **Caption:** c MRC Cognition and Brain Sciences Unit, University of Cambridge, Cambridge, UK
- **Type:** article_info_box
- **Headers:** (none)
- **Rows:** (none)
- **Notes:** Artifact: article_info_box, not a data table
- **Verified:** false

---

## table_1 (p15) — Table 1 Model variables

- **Caption:** Table 1 Model variables.
- **Columns:** 3
- **Rows:** 6
- **Notes:** Table continues on next page. The header 'Model specification for explore-exploit task (described in detail Section 3)' spans column 3. Row content with numbered lists represents multi-line cell content joined with spaces; newlines used here for readability only.
- **Footnotes in GT:** (stored in notes, see table_2 for footnote text)
- **Verified:** false

**Headers:**

1. Model variable*
2. General definition
3. Model specification for explore–exploit task (described in detail Section 3)

### Row 1

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model variable* | oτ |
| 2 | General definition | Observable outcomes at time τ. |
| 3 | Model specification | Outcome modalities: 1. Hints (no hint, hint-left, hint-right) 2. Reward (start, lose, win) 3. Observed behavior (start, take hint, choose left, choose right) |

### Row 2

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model variable* | sτ |
| 2 | General definition | Hidden states at time τ. One vector of possible state values for each state factor (i.e., each independent set of states; e.g. visual vs. auditory states). |
| 3 | Model specification | Hidden state factors: 1. Context (left machine is better vs. right machine is better) 2. Choices (start, take hint, choose left, choose right) |

### Row 3

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model variable* | π |
| 2 | General definition | A vector encoding the distribution over policies reflecting the predicted value of each policy. Each policy is a series of allowable actions in a vector if, where actions correspond to different state transitions (i.e., different Bτ,π matrices) that can be chosen by the agent for each state factor. Policies are chosen by sampling from this distribution. |
| 3 | Model specification | Allowable policies include the decision to: 1. Stay in the start state 2. Get the hint and then choose the left machine 3. Get the hint and then choose the right machine 4. Immediately choose the left machine (and then return to the start state) 5. Immediately choose the right machine (and then return to the start state) |

### Row 4

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model variable* | A matrix: p(oτ\|sτ) |
| 2 | General definition | A matrix encoding beliefs about the relationship between hidden states and observable outcomes at each time point τ (i.e., the probability that specific outcomes will be observed given specific hidden states at specific times). Note that in the POMDP literature typically used in the active inference literature (and which we describe in this tutorial), the likelihood is assumed to remain constant across time points in a trial, and hence will not differ at different values for τ (although one could adjust this if so desired). The likelihood is also assumed to be identical across policies, and so there is no indexing with respect to π. When there is more than one outcome modality, there is one A matrix per outcome modality. When there is more than one state factor, these matrices become high-dimensional and are technically referred to as tensors. For example, a second state factor corresponds to a third matrix dimension, a third state factor corresponds to a fourth matrix dimension, and so forth. |
| 3 | Model specification | Encodes beliefs about the relationship between: 1. Probability that the hint is accurate in each context 2. Probability of reward in each context 3. Identity mapping between choice states and observed behavior |

### Row 5

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model variable* | Bτ,π matrix: p(sτ+1\|sτ, π) |
| 2 | General definition | A matrix encoding beliefs about how hidden states will evolve over time (transition probabilities). For states that are under the control of the agent, there are multiple Bτ,π matrices, where each matrix corresponds to one action (state transition) that the agent may choose at a given time point (if consistent with an allowable policy). When there is more than one hidden state factor, there is one or more Bτ,π matrices per state factor (depending on policies). |
| 3 | Model specification | Encodes beliefs that: 1. Context does not change within a trial 2. Transitions from any choice state to any other are possible, depending on the policy. |

### Row 6

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model variable* | C matrix: p(oτ\|C) |
| 2 | General definition | A matrix in which some observed outcomes are preferred over others (technically modeled as prior expectations over outcomes). When there is more than one outcome modality, there is one C matrix per outcome modality. Rows indicate possible observations; columns indicate time points. Note that each column of values in C is passed through a softmax function (transforming it into a proper probability distribution) and then log-transformed (using the natural log). Thus, preferences become log-probabilities over outcomes. |
| 3 | Model specification | Encodes the stronger preference for wins than loses. Wins are also more preferred at the second time point than the third time point. |

---

## table_2 (p16) — Table 1 (continued)

- **Caption:** Table 1 (continued).
- **Columns:** 3
- **Rows:** 2
- **Notes:** Continuation of Table 1 from page 15. Footnote: *While, for consistency, we have used the standard notation found in the active inference literature, it is important to note that it does not always clearly distinguish between distributions and the possible values taken by random variables under those distributions. For example, π refers to the distribution over policies, but when... (text truncated at page bottom).
- **Verified:** false

**Headers:**

1. Model variable*
2. General definition
3. Model specification for explore–exploit task (described in detail Section 3)

### Row 1

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model variable* | D vector: p(s₁) |
| 2 | General definition | A vector encoding beliefs about (a probability distribution over) initial hidden states. When there is more than one hidden state factor, there is one D vector per state factor. |
| 3 | Model specification | The agent begins in an initial state of maximal uncertainty about the context state (prior to learning), but complete certainty that it will start in the 'start' choice state. |

### Row 2

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model variable* | E vector: p(π) |
| 2 | General definition | A distribution encoding beliefs about what policies will be chosen a priori (a prior probability distribution over policies, implemented as a vector assigning one value to each policy), based on the number of times different actions have been chosen in the past. |
| 3 | Model specification | The agent has no initial habits to choose one slot machine or another (prior to learning). |

---

## table_3 (p18) — Table 2 Matrix formulation of equations used for inference

- **Caption:** Table 2 Matrix formulation of equations used for inference.
- **Columns:** 4
- **Rows:** 3
- **Notes:** Table continues on next page. Equations contain mathematical notation including subscripts, superscripts, and Greek symbols. Multi-line cell content joined with spaces; newlines used here for readability.
- **Verified:** false

**Headers:**

1. Model update component
2. Update equation
3. Explanation
4. Model-specific description for explore-exploit task (described in detail Section 3)

### Row 1

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model update component | Updating beliefs about initial states expected under each allowable policy |
| 2 | Update equation | sτ=1,π = σ(ln D + lnᵀ Aᵒ oτ=1) / sτ=1,π ← σ( (ln D + ᵀAᵒ ln sτ=2,π) ) / ⋮ / τ=1 ← σ( ¼ (ln D + ᵀAᵒ ln sτ+1,π + lnAᵒ oτ=1) ) |
| 3 | Explanation | First equation: The variable sτ=1,π is the state prediction error with respect to the first time point in a trial. Minimizing this error corresponds to minimizing VFE (via gradient descent) and is used to update posterior beliefs over states. The term (ln D + lnᵀ Aτ=1) corresponds to prior beliefs in Bayesian inference, based on beliefs about the probability of initial hidden states, D, and the probability of transitions to future states under a policy, lnᵀ Bτ,π sτ+1. The term Aᵒ oτ corresponds to the likelihood term in Bayesian evaluation of the most consistent observed outcomes with each possible state. The term ln sτ+1,π corresponds to posterior beliefs over states (for the first time point in a trial) at the current update iteration. Second Equation: We move to the solution for the posterior, sτ=1,π, by setting ετ=1 = 0, solving for ln sτ=1,π, and then taking the softmax (normalized exponential) function (denoted σ) to ensure that the posterior over states is a proper probability distribution with non-negative values that sums to 1. This equation is described in more detail in the main text. A numerical example of the softmax function is also shown in Appendix A. |
| 4 | Model-specific description | Updating beliefs about: 1. Whether the left vs. right slot machine is more likely to pay out on a given trial. 2. The initial choice state (here, always the 'start' state). |

### Row 2

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model update component | Updating beliefs about all states after the first time point in a trial that are expected under each allowable policy |
| 2 | Update equation | sτ,π = σ(lnᵀ Bτ−1,π sτ−1,π + lnAᵒ oτ + ln Bτ,π sτ+1,π) / ετ,π ← ln sτ,π − (lnᵀ Bτ−1,π sτ−1,π + lnᵀ Bτ,π sτ+1,π + lnAᵒ oτ) / sτ,π ← σ( (lnᵀ Bτ−1,π sτ−1,π + lnAᵒ oτ + ln Bτ,π sτ+1,π) ) |
| 3 | Explanation | First equation: The variable ετ,π is the state prediction error with respect to all states in a trial after the first time point. Minimizing this error corresponds to minimizing VFE (via gradient descent) and is used to update posterior beliefs over states. The term (lnᵀ Bτ−1,π sτ−1,π + ln Bτ,π sτ+1,π) corresponds to prior beliefs in Bayesian inference, based on beliefs about the probability of transitions from past states, lnᵀ Bτ−1,π sτ−1,π, and the probability of transitions to future states under a policy, ln Bτ,π sτ+1,π. In Aᵒ oτ corresponds to the likelihood term in Bayesian inference, evaluating how consistent the observations are with each possible state. Second Equation: As in the previous row, we move to the solution for the posterior, sτ,π, by setting ετ,π = 0, solving for ln sτ,π, and then taking the softmax (σ) function. This equation is described in more detail in the main text. |
| 4 | Model-specific description | Updating beliefs about: 1. Whether the left vs. right slot machine is more likely to pay out on a given trial. 2. Beliefs about choice states at each time point (here, this depends on the choice to take the hint or select one of the slot machines). |

### Row 3

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model update component | Probability of selecting each allowable policy |
| 2 | Update equation | ππ ∝ σ(ln E − γG) |
| 3 | Explanation | The initial distribution over policies before making any observations (π₀) and the posterior distribution over policies after an observation (π₁). The initial distribution is made up of the learned prior over policies encoded in the E vector (reflecting the number of times a policy has previously been chosen) and the expected free energy of each allowable policy (G). The posterior distribution is determined by F, G, and the variational free energy (F) under each policy after making a new observation. The influence of G is also modulated by the expected precision term (γ) which encodes prior strength of belief in G. (described further in the main text; also see Fig. 9). See row 1 for an explanation of the function of the σ symbol. We note, however, that incorporation of E, F, and/or γ when computing π is a modeling choice. These need not be included in all cases (e.g., see top left portion of Fig. 9; also see Da Costa, Parr et al., 2020). In some contexts, one might choose to include some of these terms but not others, or to only include G. This depends on the research question (e.g., F will be useful if task behavior is influenced by habits, while F/γ can be useful when there are many possible deep policies to choose from). See the row in this table on 'Expected free energy precision' for more details about inference policies when F/γ are included. This is also discussed further in the main text. |
| 4 | Model-specific description | Updating overall beliefs about whether the best course of action is to take the hint and/or to choose the left vs. right slot machine. |

---

## table_4 (p19) — Table 2 (continued)

- **Caption:** Table 2 (continued).
- **Columns:** 4
- **Rows:** 2
- **Notes:** Table continues on next page. Equations contain complex mathematical notation. Multi-line cell content joined with spaces; newlines used here for readability.
- **Verified:** false

**Headers:**

1. Model update component
2. Update equation
3. Explanation
4. Model-specific description for explore-exploit task (described in detail Section 3)

### Row 1

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model update component | Expected free energy of each allowable policy |
| 2 | Update equation | Gπ = D_KL [ln q(o\|π) ‖ p(o\|C)] − E_KL[H[p(o\|π)]] / Gπ = −∑[Asτ,π · (ln Asτ,π − ln Cτ)] − diag(Aᵀ ln A) · sτ,π |
| 3 | Explanation | The first equation reproduces the 'risk + ambiguity' expression for the expected free energy of each policy (Gπ) that is explained in the main text. The second equation shows this same expression in terms of the elements in the POMDP model used in this tutorial (i.e., in matrix notation). Expected free energy evaluates the value of each policy based on their expected ability to: (1) generate the most desired outcomes, and (2) minimize uncertainty about hidden states. Achieving the most desired outcomes corresponds to minimizing the KL divergence between preferred observations, p(o\|C) = Cτ, and the observations expected under each policy. Minimizing uncertainty corresponds to minimizing the KL divergence of the likelihood (E_KL[H[p(o\|π)]]) = −diag(Aᵀ ln A) · sτ,π. Note that the diag( ) function simply takes the diagonal elements of a matrix and places them in a row vector. This is simply a convenient method for extracting and operating on the correct matrix entries to evaluate the entropy, H[p(o\|π)] = −∑ p(o) ln p(o\|s), of the distributions encoded within each column in A. For simple numerical examples of calculating the risk and ambiguity terms, see discussion of 'outcome prediction errors' in Section 2.4. |
| 4 | Model-specific description | The 'risk' term − D_KL [ln q(o\|π\|C)] = − Asτ,π · (ln Asτ,π − ln Cτ) − drives the agent to select the slot machine expected to be most likely to pay out. If the value of winning money in Cτ is high enough (i.e., if p(o\|C) is sufficiently precise), this will deter the agent from choosing to ask for the hint. The 'ambiguity' term − E_KL [H[p(o\|π)]] = − diag(Aᵀ ln A) · sτ,π − drives the agent to minimize uncertainty by asking for the hint. |

### Row 2

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model update component | Marginal free energy of each allowable policy |
| 2 | Update equation | Fπ = E_KL_τ [∑τ ln q (sτ\|π)] − ½ E_KL_τ−1,π [ln p (sτ\|sτ−1,τ, π)] − ½ E_KL_τ+1,π [ln p (sτ+1\|sτ, τ, π)] − E_KL_τ,π [ln p (oτ\|sτ, τ, π)] − ln Aᵒᵀ oτ / Fπ = ∑ sτ,π · (ln sτ,π − (ln Bτ−1 sτ−1,π + ½ ln Aᵒᵀ oτ + ½ ln Bτ sτ+1,π) + (ln Bτ−1 sτ−1,π + ½ ln Bτ−1 sτ−1,π) − ln Aᵒᵀ oτ) |
| 3 | Explanation | The first equation reproduces the marginal (as opposed to variational) free energy, which is now used in the most recent implementations of active inference. The second equation shows this same expression in terms of the elements in the POMDP model used in this tutorial (i.e., in matrix notation). Marginal free energy has a slightly different form than the expressions for VFE that are also shown in the text (and which have been used in many previous papers in the active inference literature). This updated form improves on certain limitations of the message passing algorithms described in minimization of VFE (see Section 2.3; also see Parr, Markovic, Kiebel, & Friston, 2019). Marginal free energy evaluates the evidence that inferred states provide for each policy (based on new observations at each time point). See the first two rows in this table on updating beliefs about states for an explanation of how each term in the equation relates to Bayesian inference. |
| 4 | Model-specific description | This would encode the amount of surprise (given a choice of policy) when observing a hint or a win/loss after selecting a specific slot machine. |

---

## table_5 (p20) — Table 2 (continued)

- **Caption:** Table 2 (continued).
- **Columns:** 4
- **Rows:** 1
- **Notes:** This is the final row of Table 2. Table note at bottom of page: 'The term Bᵀτ denotes the transpose of Bτ, with normalized columns (i.e., columns that sum to 1). Note that you may commonly see the dot (.) notation used in the active inference literature to denote transposed matrix multiplication, such that Bᵀ... which means Aᵀ... (see the latex section here...' (truncated at page bottom).
- **Verified:** false

**Headers:**

1. Model update component
2. Update equation
3. Explanation
4. Model-specific description for explore-exploit task (described in detail Section 3)

### Row 1

| Col | Header | Content |
|-----|--------|---------|
| 1 | Model update component | Expected free energy precision |
| 2 | Update equation | p(γ) = Γ(1, β) / E[γ] = 1/β / Iterated to convergence: / πᵇ ← σ(ln E − γG) / Gτˊˊ ← (πᵇ − π₀) · (−G) / βˢᵃˊˊ ← β + βˢᵃˊˊ / γ ← 1/β |
| 3 | Explanation | The β term, and its prior value β₀, is a hyperparameter on the expected free energy precision term (γ). Specifically, β is the 'rate' parameter of a gamma distribution (T) with a 'shape' parameter value of 1. The expected value of this distribution, E[γ] = γ, is equal to the reciprocal of β. Note that we use the non-italicized γ to refer to the matrix and that we use the italicized γ to refer to the scalar value of that variable. This scalar is what is subsequently updated based on the equations shown here. The γ term controls the precision of G, based on the agent's confidence in its estimates of expected free energy. This confidence changes when new observations are consistent or inconsistent with G. More specifically, γ modulates the influence of G on policy selection based on a G prediction error (εγˊˊ). This is calculated based on the difference between the initial distribution over policies (π₀) and the posterior distribution after making a new observation (πᵇ). The difference between these terms reflects the extent to which new observations (scored by F) make policies more or less likely. If the vector encoding the posterior over policies increases in magnitude in comparison to the prior, and still points in the same direction, the angle between the posterior and the prior will point in the same direction as the −G vector (i.e., less than a 90° angle apart; see Fig. 9). If so, the value of γ will increase, thereby increasing the impact of G on policy selection. In contrast, if the difference vector between the posterior and the prior does not point in the same direction as the −G vector (i.e., greater than a 90° angle apart), γ will decrease and thereby reduce the impact of G on policy selection (i.e., as the agent's confidence in its estimates of expected free energy has decreased). Note that the βˢᵃˊˊ term mediating these updates technically corresponds to the gradient of free energy with respect to γ (∇γF). The subsequent update in the value of γ is such that G contributes to the posterior probability of policies in an optimal manner. β and γ are often discussed in relation to dopamine in the active inference literature. Note that β₀ is the initial prior (which is not updated), and β is the initial posterior, which is subsequently updated to provide a new estimate for γ = 1/β. The variable φ is a step size parameter that reduces the magnitude of each update and promotes stable convergence to final values of γ. For a derivation of these equations, see Appendix in Sales, Friston, Jones, Pickering, and Moran (2019). |
| 4 | Model-specific description | A higher value for β would reduce an agent's confidence in the best policy based on the values in G. This might lead the agent to select a slot machine more randomly or based to a greater extent on its past choices (i.e., if it has a precise prior over policies in the vector E). |

---

## table_6 (p30) — Table 3 Output fields for spm_MDP_VB_X_tutorial.m

- **Caption:** Table 3 Output fields for spm_MDP_VB_X_tutorial.m simulation script.
- **Columns:** 4
- **Rows:** 11
- **Notes:** Table continues on next page. The table has 4 columns: MDP Field, Model Element, Structure, Description.
- **Verified:** false

**Headers:**

1. MDP Field
2. Model Element
3. Structure
4. Description

| MDP Field | Model Element | Structure | Description |
|-----------|--------------|-----------|-------------|
| MDP.F | Negative variational free energy of each policy over time. | Rows = policies. Columns = time points. | Negative variational free energy of each policy at each time point in the trial. For example, if there are 2 policies and 6 time points there will be a 2 × 6 matrix containing the variational free energy of each policy at each point in the trial. |
| MDP.G | Negative expected free energy of each policy over time. | Rows = policies. Columns = time points. | Negative expected free energy of each policy at each time point in the trial. For example, if there are 2 policies and 6 time points there will be a 2 × 6 matrix containing the negative expected free energy of each policy at each point in the trial. |
| MDP.H | Total negative variational free energy over time. | Columns = time points. | Total negative variational free energy averaged across states and policies at each time point. For example, if there are 8 time points there will be a 1 × 8 row vector containing the total negative free energy at each time point. |
| MDP.Fa MDP.Fd MDP.Fb ... | MDP.Fa is the negative free energy of parameters 'a' (if learning A matrix). There are also analogous fields if learning other matrices/vectors (e.g. MDP.Fd for learning the parameters of the D vector, etc.). | Columns = one per outcome modality or hidden state factor (i.e., depending on the specific parameters being learned). If the agent is learning parameters of a single vector (e.g., E), this will be a single column. | |
| MDP.o | Outcome vectors. | Rows = outcome modalities. Columns = time points. | Vectors (one per cell) specifying the outcomes for each modality at each time point. Observed outcomes are encoded as 1s, with 0s otherwise. |
| MDP.P | Probability of emitting an action. | Rows = one per controllable state factor. Columns = time points. Third dimension = time point. | The probability of emitting each particular action, expressed as a softmax function of a vector containing the posterior over policies. The action summed over each policy. For example, suppose that there are 2 allowable actions for a posterior over policies of [.4 .2], with policy 1 leading to action 1, and policy 1 leading to action 2. The probability of action 1 and 2 is therefore [.8 .2]. This vector is then passed through another softmax function controlled by the inverse temperature parameter α, which by default is extremely large (α = 512). Actions are then sampled from the resulting distribution, where higher α values promote more deterministic action selection (i.e., by choosing the action with the highest probability). |
| MDP.Q | Posteriors over states under each policy at the end of the trial. | 1 cell per state factor. Rows = states. Columns = time points. Third dimension = policy number. | Posterior probability of each state conditioned on each policy at the end of the trial, after successive rounds of updating at each time point. |
| MDP.R | Posteriors over policies. | Rows = policies. Columns = time points. | Posterior over policies at each time point. |
| MDP.X | Posteriors over all states at the end of the trial. These are Bayesian model averages of the posteriors over states under each policy. | 1 cell per state factor. Rows = states. Columns = time points. | This means taking a weighted average of the posteriors over states under each policy, weighted by the posterior probability of each policy. |
| MDP.un | Neuronal encoding of policies. | 1 cell per policy dimension. Rows = policies. Columns = iterations of message passing (16 per time point). For example, 16 iterations and 8 time points gives a vector with 128 elements. | Simulated neuronal encoding of the posterior probability of each policy at each iteration of message passing. |
| MDP.vn | Neuronal encoding of state prediction errors. | 1 cell per state factor. Rows = iterations of message passing (16 per time point). Columns = states. Third Dimension: time point the belief is about (τ). Fourth Dimension: time point the belief is at (t). | Bayesian model average of normalized firing rates (i.e., reflecting posteriors over states at each iteration of message passing (weighted by the posterior probability of the associated policies). |

---

## table_7 (p31) — Table 3 (continued)

- **Caption:** Table 3 (continued).
- **Columns:** 4
- **Rows:** 4
- **Notes:** Continuation of Table 3 from page 30. Page bottom contains a footnote (partially visible): 'Constant α = 512...' with similar direction notation.
- **Verified:** false

**Headers:**

1. MDP Field
2. Model Element
3. Structure
4. Description

| MDP Field | Model Element | Structure | Description |
|-----------|--------------|-----------|-------------|
| MDP.xn | Neuronal encoding of hidden states. | 1 cell per state factor. Rows = iterations of message passing (16 per time point). Columns = states. Third Dimension: time point the belief is about (τ). Fourth Dimension: time point the belief is at (t). | Bayesian model average of normalized firing rates which reflect posteriors over states at each iteration of message passing (weighted by the posterior probability of the associated policies). |
| MDP.wn | Neuronal encoding of tonic dopamine, reflecting the current value of γ. | Rows = number of iterative updates (16 per time point). For example, if there were two time points in a trial this would be 1 column with 32 rows. | This reflects the value of the expected precision of the expected free energy over policies (γ) at each iteration of updating. |
| MDP.dn | Neuronal encoding of phasic dopamine responses, reflecting the rate of change in γ. | Rows = number of iterative updates (16 per time point). For example, if there were two time points in a trial this would be 1 column with 32 rows. | This variable reflects the expected precision of change in expected free energy over policies (γ) at each iteration of updating. |
| MDP.rt | Simulated reaction times. | Columns = time points. | Computation time (i.e., time to convergence) for each round of message passing and action selection. |

---

## Review Checklist

- [ ] table_0 — artifact confirmed
- [ ] table_1 — 6 rows, 3 cols verified
- [ ] table_2 — 2 rows, 3 cols verified (+ footnote text)
- [ ] table_3 — 3 rows, 4 cols verified (check σ vs s in equations)
- [ ] table_4 — 2 rows, 4 cols verified
- [ ] table_5 — 1 row, 4 cols verified (+ table footnote text)
- [ ] table_6 — 11 rows, 4 cols verified
- [ ] table_7 — 4 rows, 4 cols verified
