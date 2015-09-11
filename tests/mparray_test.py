# encoding: utf-8
# FIXME Is there a better metric to compare two arrays/scalars than
#       assert_(array)_almost_equal? Something that takes magnitude into
#       account?

from __future__ import absolute_import, division, print_function

import numpy as np
import pytest as pt
from numpy.linalg import svd
from numpy.testing import assert_array_almost_equal, assert_array_equal, \
    assert_almost_equal, assert_equal
from six.moves import range

import mpnum.factory as factory
import mpnum.mparray as mp
from mpnum._tools import global_to_local, local_to_global
from mpnum import _tools


# nr_sites, local_dim, bond_dim
MP_TEST_PARAMETERS = [(6, 2, 4), (4, 3, 5), (5, 2, 1)]
# nr_sites, local_dim, bond_dim, sites_per_group
MP_TEST_PARAMETERS_GROUPS = [(6, 2, 4, 3), (6, 2, 4, 2), (4, 3, 5, 2)]


# We choose to use a global reperentation of multipartite arrays throughout our
# tests to be consistent and a few operations (i.e. matrix multiplication) are
# easier to express
def mpo_to_global(mpo):
    return local_to_global(mpo.to_array(), len(mpo))


###############################################################################
#                         Basic creation & operations                         #
###############################################################################
@pt.mark.parametrize('nr_sites, local_dim, _', MP_TEST_PARAMETERS)
def test_from_full(nr_sites, local_dim, _):
    psi = factory.random_vec(nr_sites, local_dim)
    mps = mp.MPArray.from_array(psi, 1)
    assert_array_almost_equal(psi, mps.to_array())

    op = factory.random_op(nr_sites, local_dim)
    mpo = mp.MPArray.from_array(op, 2)
    assert_array_almost_equal(op, mpo.to_array())


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_from_kron(nr_sites, local_dim, bond_dim):
    plegs = 2
    factors = tuple(factory._zrandn([nr_sites] + ([local_dim] * plegs)))
    op = _tools.mkron(*factors)
    op.shape = [local_dim] * (plegs * nr_sites)
    mpo = mp.MPArray.from_kron(factors)
    assert_array_almost_equal(op, mpo_to_global(mpo))


@pt.mark.parametrize('nr_sites, local_dim, _', MP_TEST_PARAMETERS)
def test_conjugations(nr_sites, local_dim, _):
    op = factory.random_op(nr_sites, local_dim)
    mpo = mp.MPArray.from_array(op, 2)
    assert_array_almost_equal(np.conj(op), mpo.conj().to_array())


@pt.mark.parametrize('nr_sites, local_dim, _', MP_TEST_PARAMETERS)
def test_transposition(nr_sites, local_dim, _):
    op = factory.random_op(nr_sites, local_dim)
    mpo = mp.MPArray.from_array(global_to_local(op, nr_sites), 2)

    opT = op.reshape((local_dim**nr_sites,) * 2).T \
        .reshape((local_dim,) * 2 * nr_sites)
    assert_array_almost_equal(opT, mpo_to_global(mpo.T()))


###############################################################################
#                            Algebraic operations                             #
###############################################################################
@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_dot(nr_sites, local_dim, bond_dim):
    mpo1 = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op1 = mpo_to_global(mpo1)
    mpo2 = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op2 = mpo_to_global(mpo2)

    # Dotproduct of all 1st physical with 0th physical legs = np.dot
    dot_np = np.tensordot(op1.reshape((local_dim**nr_sites, ) * 2),
                          op2.reshape((local_dim**nr_sites, ) * 2),
                          axes=([1], [0]))
    dot_np = dot_np.reshape(op1.shape)
    dot_mp = mpo_to_global(mp.dot(mpo1, mpo2, axes=(1, 0)))
    assert_array_almost_equal(dot_np, dot_mp)
    # this should also be the default axes
    dot_mp = mpo_to_global(mp.dot(mpo1, mpo2))
    assert_array_almost_equal(dot_np, dot_mp)

    # Dotproduct of all 0th physical with 1st physical legs = np.dot
    dot_np = np.tensordot(op1.reshape((local_dim**nr_sites, ) * 2),
                          op2.reshape((local_dim**nr_sites, ) * 2),
                          axes=([0], [1]))
    dot_np = dot_np.reshape(op1.shape)
    dot_mp = mpo_to_global(mp.dot(mpo1, mpo2, axes=(0, 1)))
    assert_array_almost_equal(dot_np, dot_mp)
    # this should also be the default axes
    dot_mp = mpo_to_global(mp.dot(mpo1, mpo2, axes=(-2, -1)))
    assert_array_almost_equal(dot_np, dot_mp)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_partialdot(nr_sites, local_dim, bond_dim):
    assert nr_sites >= 2, 'test requires at least two sites'
    part_sites = nr_sites // 2
    start_at = min(2, nr_sites // 2)

    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo).reshape((local_dim**nr_sites,) * 2)
    mpo_part = factory.random_mpa(part_sites, (local_dim, local_dim), bond_dim)
    op_part = mpo_to_global(mpo_part).reshape((local_dim**part_sites,) * 2)
    op_part_embedded = np.kron(
        np.kron(np.eye(local_dim**start_at), op_part),
        np.eye(local_dim**(nr_sites - part_sites - start_at)))

    prod1 = np.dot(op, op_part_embedded)
    prod2 = np.dot(op_part_embedded, op)
    prod1_mpo = mp.partialdot(mpo, mpo_part, start_at=start_at)
    prod2_mpo = mp.partialdot(mpo_part, mpo, start_at=start_at)
    prod1_mpo = mpo_to_global(prod1_mpo).reshape((local_dim**nr_sites,) * 2)
    prod2_mpo = mpo_to_global(prod2_mpo).reshape((local_dim**nr_sites,) * 2)

    assert_array_almost_equal(prod1, prod1_mpo)
    assert_array_almost_equal(prod2, prod2_mpo)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_inner_vec(nr_sites, local_dim, bond_dim):
    mp_psi1 = factory.random_mpa(nr_sites, local_dim, bond_dim)
    psi1 = mp_psi1.to_array().ravel()
    mp_psi2 = factory.random_mpa(nr_sites, local_dim, bond_dim)
    psi2 = mp_psi2.to_array().ravel()

    inner_np = np.vdot(psi1, psi2)
    inner_mp = mp.inner(mp_psi1, mp_psi2)
    assert_almost_equal(inner_mp, inner_np)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_inner_mat(nr_sites, local_dim, bond_dim):
    mpo1 = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op1 = mpo_to_global(mpo1).reshape((local_dim**nr_sites, ) * 2)
    mpo2 = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op2 = mpo_to_global(mpo2).reshape((local_dim**nr_sites, ) * 2)

    inner_np = np.trace(np.dot(op1.conj().transpose(), op2))
    inner_mp = mp.inner(mpo1, mpo2)
    assert_almost_equal(inner_mp, inner_np)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_norm(nr_sites, local_dim, bond_dim):
    mp_psi = factory.random_mpa(nr_sites, local_dim, bond_dim)
    psi = mp_psi.to_array()

    assert_almost_equal(mp.inner(mp_psi, mp_psi), mp.norm(mp_psi)**2)
    assert_almost_equal(np.sum(psi.conj() * psi), mp.norm(mp_psi)**2)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_normdist(nr_sites, local_dim, bond_dim):
    psi1 = factory.random_mpa(nr_sites, local_dim, bond_dim)
    psi2 = factory.random_mpa(nr_sites, local_dim, bond_dim)

    assert_almost_equal(mp.normdist(psi1, psi2), mp.norm(psi1 - psi2))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim, keep_width',
                     [(6, 2, 4, 3), (4, 3, 5, 2)])
def test_partialtrace(nr_sites, local_dim, bond_dim, keep_width):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo)

    for site in range(nr_sites - keep_width + 1):
        traceout = tuple(range(site)) \
            + tuple(range(site + keep_width, nr_sites))
        axes = [(0, 1) if site in traceout else None for site in range(nr_sites)]
        red_mpo = mp.partialtrace(mpo, axes=axes)
        red_from_op = _tools.partial_trace(op, traceout)
        assert_array_almost_equal(mpo_to_global(red_mpo), red_from_op,
                                  err_msg="not equal at site {}".format(site))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_trace(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo).reshape((local_dim**nr_sites,) * 2)

    assert_almost_equal(np.trace(op), mp.trace(mpo))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_add_and_subtr(nr_sites, local_dim, bond_dim):
    mpo1 = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op1 = mpo_to_global(mpo1)
    mpo2 = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op2 = mpo_to_global(mpo2)

    assert_array_almost_equal(op1 + op2, mpo_to_global(mpo1 + mpo2))
    assert_array_almost_equal(op1 - op2, mpo_to_global(mpo1 - mpo2))

    mpo1 += mpo2
    assert_array_almost_equal(op1 + op2, mpo_to_global(mpo1))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', [(3, 2, 2)])
def test_operations_typesafety(nr_sites, local_dim, bond_dim):
    # create a real MPA
    mpo1 = factory._generate(nr_sites, (local_dim, local_dim), bond_dim,
                             func=lambda shape: np.random.randn(*shape))
    mpo2 = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)

    assert mpo1[0].dtype == float
    assert mpo2[0].dtype == complex

    assert (mpo1 + mpo1)[0].dtype == float
    assert (mpo1 + mpo2)[0].dtype == complex
    assert (mpo2 + mpo1)[0].dtype == complex

    assert (mpo1 - mpo1)[0].dtype == float
    assert (mpo1 - mpo2)[0].dtype == complex
    assert (mpo2 - mpo1)[0].dtype == complex

    mpo1 += mpo2
    assert mpo1[0].dtype == complex


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_mult_mpo_scalar(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo)
    scalar = np.random.randn()

    assert_array_almost_equal(scalar * op, mpo_to_global(scalar * mpo))

    mpo *= scalar
    assert_array_almost_equal(scalar * op, mpo_to_global(mpo))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_div_mpo_scalar(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo)
    scalar = np.random.randn()

    assert_array_almost_equal(op / scalar, mpo_to_global(mpo / scalar))

    mpo /= scalar
    assert_array_almost_equal(op / scalar, mpo_to_global(mpo))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_outer(nr_sites, local_dim, bond_dim):
    # NOTE: Everything here is in local form!!!
    assert nr_sites > 1

    mpo = factory.random_mpa(nr_sites // 2, (local_dim, local_dim), bond_dim)
    op = mpo.to_array()

    # Test with 2-factors with full form
    mpo_double = mp.outer((mpo, mpo))
    op_double = np.tensordot(op, op, axes=(tuple(), ) * 2)
    assert len(mpo_double) == 2 * len(mpo)
    assert_array_almost_equal(op_double, mpo_double.to_array())
    assert_array_equal(mpo_double.bdims, mpo.bdims + (1,) + mpo.bdims)

    # Test 3-factors iteratively (since full form would be too large!!
    diff = mp.outer((mpo, mpo, mpo)) - mp.outer((mpo, mp.outer((mpo, mpo))))
    diff.normalize()
    assert len(diff) == 3 * len(mpo)
    assert mp.norm(diff) < 1e-6


@pt.mark.parametrize('_, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_inject(_, local_dim, bond_dim):
    # plegs = 3 is hardcoded below (argument to .transpose()).
    # Uniform local dimension is also hardcoded below (arguments to
    # .reshape()).
    plegs = 3
    local_dim = (local_dim,) * plegs

    a, b, c = factory._zrandn((3, 2) + local_dim)
    # We don't use b[1, :]
    b = b[0, :]
    # Here, only global order (as given by np.kron()).
    abbc0 = _tools.mkron(a[0, :], b, b, c[0, :])
    abbc1 = _tools.mkron(a[1, :], b, b, c[1, :])
    abbc = (abbc0 + abbc1).reshape(4 * local_dim)
    ac0 = np.kron(a[0, :], c[0, :])
    ac1 = np.kron(a[1, :], c[1, :])
    ac = (ac0 + ac1).reshape(2 * local_dim)
    ac_mpo = mp.MPArray.from_array(global_to_local(ac, sites=2), plegs)
    abbc_mpo = mp.inject(ac_mpo, pos=1, num=2, inject_ten=b)
    abbc_from_mpo = mpo_to_global(abbc_mpo)
    assert_array_almost_equal(abbc, abbc_from_mpo)

    # Here, only local order.
    ac = factory._zrandn(local_dim * 2)
    b = factory._zrandn(local_dim)
    acb = np.tensordot(ac, b, axes=((), ()))
    abc = acb.transpose((0, 1, 2, 6, 7, 8, 3, 4, 5))
    ac_mpo = mp.MPArray.from_array(ac, plegs)
    abc_mpo = mp.inject(ac_mpo, pos=1, num=1, inject_ten=b)
    # Keep local order
    abc_from_mpo = abc_mpo.to_array()
    assert_array_almost_equal(abc, abc_from_mpo)

    # plegs = 2 is hardcoded below (argument to .transpose()).
    # Uniform local dimension is also hardcoded below (arguments to
    # .reshape()).
    plegs = 2
    local_dim = (local_dim[0],) * plegs

    a, c = factory._zrandn((2, 2) + local_dim)
    b = np.eye(local_dim[0])
    # Here, only global order (as given by np.kron()).
    abbc0 = _tools.mkron(a[0, :], b, b, c[0, :])
    abbc1 = _tools.mkron(a[1, :], b, b, c[1, :])
    abbc = (abbc0 + abbc1).reshape(4 * local_dim)
    ac0 = np.kron(a[0, :], c[0, :])
    ac1 = np.kron(a[1, :], c[1, :])
    ac = (ac0 + ac1).reshape(2 * local_dim)
    ac_mpo = mp.MPArray.from_array(global_to_local(ac, sites=2), plegs)
    abbc_mpo = mp.inject(ac_mpo, pos=1, num=2, inject_ten=None)
    abbc_from_mpo = mpo_to_global(abbc_mpo)
    assert_array_almost_equal(abbc, abbc_from_mpo)

    # Here, only local order.
    ac = factory._zrandn(local_dim * 2)
    b = np.eye(local_dim[0])
    acb = np.tensordot(ac, b, axes=((), ()))
    abc = acb.transpose((0, 1, 4, 5, 2, 3))
    ac_mpo = mp.MPArray.from_array(ac, plegs)
    abc_mpo = mp.inject(ac_mpo, pos=1, num=1, inject_ten=None)
    # Keep local order
    abc_from_mpo = abc_mpo.to_array()
    assert_array_almost_equal(abc, abc_from_mpo)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim, local_width',
                     [(6, 2, 4, 3), (4, 3, 5, 2)])
def test_local_sum(nr_sites, local_dim, bond_dim, local_width):
    eye_mpa = factory.eye(1, local_dim)

    def embed_mpa(mpa, startpos):
        mpas = [eye_mpa] * startpos + [mpa] + \
               [eye_mpa] * (nr_sites - startpos - local_width)
        res = mp.outer(mpas)
        return res

    rs = np.random.RandomState(seed=0)
    nr_startpos = nr_sites - local_width + 1
    mpas = [factory.random_mpa(local_width, (local_dim,) * 2, bond_dim,
                               randstate=rs)
            for i in range(nr_startpos)]

    # Embed with mp.outer() and calculate naive MPA sum:
    mpas_embedded = [embed_mpa(mpa, i) for i, mpa in enumerate(mpas)]
    mpa_sum = mpas_embedded[0]
    for mpa in mpas_embedded[1:]:
        mpa_sum += mpa

    # Compare with local_sum: Same result, smaller bond
    # dimension.
    mpa_local_sum = mp.local_sum(mpas)

    assert all(d1 <= d2 for d1, d2 in zip(mpa_local_sum.bdims, mpa_sum.bdims))
    assert_array_almost_equal(mpa_local_sum.to_array(), mpa_sum.to_array())


###############################################################################
#                         Shape changes, conversions                          #
###############################################################################
@pt.mark.parametrize('nr_sites, local_dim, bond_dim, sites_per_group',
                     MP_TEST_PARAMETERS_GROUPS)
def test_group_sites(nr_sites, local_dim, bond_dim, sites_per_group):
    assert (nr_sites % sites_per_group) == 0, \
        'nr_sites not a multiple of sites_per_group'
    mpa = factory.random_mpa(nr_sites, (local_dim,) * 2, bond_dim)
    grouped_mpa = mpa.group_sites(sites_per_group)
    op = mpa.to_array()
    grouped_op = grouped_mpa.to_array()
    assert_array_almost_equal(op, grouped_op)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim, sites_per_group',
                     MP_TEST_PARAMETERS_GROUPS)
def test_split_sites(nr_sites, local_dim, bond_dim, sites_per_group):
    assert (nr_sites % sites_per_group) == 0, \
        'nr_sites not a multiple of sites_per_group'
    mpa = factory.random_mpa(nr_sites // sites_per_group,
                             (local_dim,) * (2 * sites_per_group), bond_dim)
    split_mpa = mpa.split_sites(sites_per_group)
    op = mpa.to_array()
    split_op = split_mpa.to_array()
    assert_array_almost_equal(op, split_op)


###############################################################################
#                         Normalization & Compression                         #
###############################################################################
def assert_lcannonical(ltens, msg=''):
    ltens = ltens.reshape((np.prod(ltens.shape[:-1]), ltens.shape[-1]))
    prod = ltens.conj().T.dot(ltens)
    assert_array_almost_equal(prod, np.identity(prod.shape[0]),
                              err_msg=msg)


def assert_rcannonical(ltens, msg=''):
    ltens = ltens.reshape((ltens.shape[0], np.prod(ltens.shape[1:])))
    prod = ltens.dot(ltens.conj().T)
    assert_array_almost_equal(prod, np.identity(prod.shape[0]),
                              err_msg=msg)


def assert_correct_normalzation(mpo, lnormal_target, rnormal_target):
    lnormal, rnormal = mpo.normal_form

    assert_equal(lnormal, lnormal_target)
    assert_equal(rnormal, rnormal_target)

    for n in range(lnormal):
        assert_lcannonical(mpo[n], msg="Failure left cannonical (n={}/{})"
                           .format(n, lnormal_target))
    for n in range(rnormal, len(mpo)):
        assert_rcannonical(mpo[n], msg="Failure right cannonical (n={}/{})"
                           .format(n, rnormal_target))


@pt.mark.parametrize('nr_sites, local_dim, _', MP_TEST_PARAMETERS)
def test_normalization_from_full(nr_sites, local_dim, _):
    op = factory.random_op(nr_sites, local_dim)
    mpo = mp.MPArray.from_array(op, 2)
    assert_correct_normalzation(mpo, nr_sites - 1, nr_sites)


# FIXME Add counter to normalization functions
@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_normalization_incremental(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo)
    assert_correct_normalzation(mpo, 0, nr_sites)
    assert_array_almost_equal(op, mpo_to_global(mpo))

    for site in range(1, nr_sites):
        mpo.normalize(left=site)
        assert_correct_normalzation(mpo, site, nr_sites)
        assert_array_almost_equal(op, mpo_to_global(mpo))

    for site in range(nr_sites - 1, 0, -1):
        mpo.normalize(right=site)
        assert_correct_normalzation(mpo, site - 1, site)
        assert_array_almost_equal(op, mpo_to_global(mpo))


# FIXME Add counter to normalization functions
@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_normalization_jump(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo)
    assert_correct_normalzation(mpo, 0, nr_sites)
    assert_array_almost_equal(op, mpo_to_global(mpo))

    center = nr_sites // 2
    mpo.normalize(left=center - 1, right=center)
    assert_correct_normalzation(mpo, center - 1, center)
    assert_array_almost_equal(op, mpo_to_global(mpo))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_normalization_full(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo)
    assert_correct_normalzation(mpo, 0, nr_sites)
    assert_array_almost_equal(op, mpo_to_global(mpo))

    mpo.normalize(right=1)
    assert_correct_normalzation(mpo, 0, 1)
    assert_array_almost_equal(op, mpo_to_global(mpo))

    ###########################################################################
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo)
    assert_correct_normalzation(mpo, 0, nr_sites)
    assert_array_almost_equal(op, mpo_to_global(mpo))

    mpo.normalize(left=len(mpo) - 1)
    assert_correct_normalzation(mpo, len(mpo) - 1, len(mpo))
    assert_array_almost_equal(op, mpo_to_global(mpo))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_normalization_default_args(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    assert_correct_normalzation(mpo, 0, nr_sites)

    mpo.normalize(left=1)
    mpo.normalize()
    assert_correct_normalzation(mpo, nr_sites - 1, nr_sites)

    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    assert_correct_normalzation(mpo, 0, nr_sites)

    mpo.normalize(left=1)
    mpo.normalize(right=nr_sites - 2)
    mpo.normalize()
    assert_correct_normalzation(mpo, 0, 1)


def test_normalization_compression():
    """If the bond dimension is too large at the boundary, qr decompostion
    in normalization may yield smaller bond dimension"""
    mpo = factory.random_mpa(sites=2, ldim=2, bdim=20)
    mpo.normalize(right=1)
    assert_correct_normalzation(mpo, 0, 1)
    assert mpo.bdims[0] == 2

    mpo = factory.random_mpa(sites=2, ldim=2, bdim=20)
    mpo.normalize(left=1)
    assert_correct_normalzation(mpo, 1, 2)
    assert mpo.bdims[0] == 2


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_mult_mpo_scalar_normalization(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    op = mpo_to_global(mpo)
    scalar = np.random.randn()

    center = nr_sites // 2
    mpo.normalize(left=center - 1, right=center)
    mpo_times_two = scalar * mpo

    assert_array_almost_equal(scalar * op, mpo_to_global(mpo_times_two))
    assert_correct_normalzation(mpo_times_two, center - 1, center)

    mpo *= scalar
    assert_array_almost_equal(scalar * op, mpo_to_global(mpo))
    assert_correct_normalzation(mpo, center - 1, center)


#####################
#  SVD compression  #
#####################
@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_svd_trivial(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)

    mpo_new = mpo.copy()
    mpo_new.compress_svd(bdim=10 * bond_dim, direction='right')
    assert_array_equal(mpo.bdims, mpo_new.bdims)
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))

    mpo_new = mpo.copy()
    mpo_new.compress_svd(bdim=10 * bond_dim, direction='left')
    assert_array_equal(mpo.bdims, mpo_new.bdims)
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_svd_hard_cutoff(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    zero = factory.zero(nr_sites, (local_dim, local_dim), bond_dim)
    mpo_new = mpo + zero

    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
    for bdims in zip(mpo.bdims, zero.bdims, mpo_new.bdims):
        assert_equal(bdims[0] + bdims[1], bdims[2])

    # Right-compression
    mpo_new = mpo + zero
    overlap = mpo_new.compress_svd(bdim=bond_dim, direction='right')
    assert_array_equal(mpo_new.bdims, bond_dim)
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
    assert_correct_normalzation(mpo_new, nr_sites - 1, nr_sites)
    # since no truncation error should occur
    assert_almost_equal(overlap, mp.norm(mpo)**2, decimal=5)

    # Left-compression
    mpo_new = mpo + zero
    overlap = mpo_new.compress_svd(bdim=bond_dim, direction='left')
    assert_array_equal(mpo_new.bdims, bond_dim)
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
    assert_correct_normalzation(mpo_new, 0, 1)
    # since no truncation error should occur
    assert_almost_equal(overlap, mp.norm(mpo)**2, decimal=5)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_svd_relerr(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    zero = factory.zero(nr_sites, (local_dim, local_dim), bond_dim)
    mpo_new = mpo + zero

    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
    for bdims in zip(mpo.bdims, zero.bdims, mpo_new.bdims):
        assert_equal(bdims[0] + bdims[1], bdims[2])

    # Right-compression
    mpo_new = mpo + zero
    mpo_new.compress_svd(relerr=1e-6, direction='right')
    assert_array_equal(mpo_new.bdims, bond_dim)
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
    assert_correct_normalzation(mpo_new, nr_sites - 1, nr_sites)

    # Left-compression
    mpo_new = mpo + zero
    mpo_new.compress_svd(relerr=1e-6, direction='left')
    assert_array_equal(mpo_new.bdims, bond_dim)
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
    assert_correct_normalzation(mpo_new, 0, 1)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_svd_overlap(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    mpo_new = mpo.copy()

    # Catch superficious compression paramter
    max_bdim = max(bond_dim // 2, 1)

    overlap = mpo_new.compress_svd(bdim=max_bdim, direction='right')
    assert_almost_equal(overlap, mp.inner(mpo, mpo_new), decimal=5)
    assert all(bdim <= max_bdim for bdim in mpo_new.bdims)

    mpo_new = mpo.copy()
    overlap = mpo_new.compress_svd(bdim=max_bdim, direction='left')
    assert_almost_equal(overlap, mp.inner(mpo, mpo_new), decimal=5)
    assert all(bdim <= max_bdim for bdim in mpo_new.bdims)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_svd_compare(nr_sites, local_dim, bond_dim):
    randstate = np.random.RandomState(seed=46)
    mpa = factory.random_mpa(nr_sites, (local_dim,) * 2, bond_dim, randstate)
    target_bonddim = max(2 * bond_dim // 3, 1)
    directions = ('left', 'right')
    for direction in directions:
        target_array = _svd_compression_full(mpa, direction, target_bonddim)
        mpa_compr = mpa.copy()
        mpa_compr.compress_svd(bdim=target_bonddim, direction=direction)
        array_compr = mpa_compr.to_array()
        assert_array_almost_equal(
            target_array, array_compr,
            err_msg='direction {0!r} failed'.format(direction))


############################
# Variational compression  #
############################
@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_var_trivial(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)

    # using internal initial vector
    mpo_new = mpo.compress_var(bdim=10 * bond_dim)
    # since var. compression doesnt take into account the original bond dim
    assert all(d1 <= d2 for d1, d2 in zip(mpo.bdims, mpo_new.bdims))
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))

    # using an external initial vector
    initmpa = factory.random_mpa(nr_sites, (local_dim, ) * 2, 10 * bond_dim)
    initmpa *= mp.norm(mpo) / mp.norm(initmpa)
    mpo_new = mpo.compress_var(initmpa=initmpa)
    assert all(d1 <= d2 for d1, d2 in zip(mpo.bdims, mpo_new.bdims))
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_var_hard_cutoff(nr_sites, local_dim, bond_dim):
    mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
    zero = factory.zero(nr_sites, (local_dim, local_dim), bond_dim)
    mpo_new = mpo + zero

    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
    for bdims in zip(mpo.bdims, zero.bdims, mpo_new.bdims):
        assert_equal(bdims[0] + bdims[1], bdims[2])

    mpo_new = mpo + zero
    initmpa = factory.random_mpa(nr_sites, (local_dim, ) * 2, bond_dim)
    mpo_new = mpo_new.compress_var(initmpa=initmpa)
    #  overlap = mpo_new.compress(bdim=bond_dim, method='var')
    assert_array_equal(mpo_new.bdims, bond_dim)
    assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
    # FIXME assert_correct_normalzation(mpo_new, nr_sites - 1, nr_sites)
    # since no truncation error should occur
    # FIXME assert_almost_equal(overlap, mp.norm(mpo)**2, decimal=5)

# FIXME
#  @pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
#  def test_compression_var_relerr(nr_sites, local_dim, bond_dim):
#      mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
#      zero = factory.zero(nr_sites, (local_dim, local_dim), bond_dim)
#      mpo_new = mpo + zero

#      assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
#      for bdims in zip(mpo.bdims, zero.bdims, mpo_new.bdims):
#          assert_equal(bdims[0] + bdims[1], bdims[2])

#      # Right-compression
#      mpo_new = mpo + zero
#      mpo_new.compress(relerr=1e-6, method='var', direction='right')
#      assert_array_equal(mpo_new.bdims, bond_dim)
#      assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
#      assert_correct_normalzation(mpo_new, nr_sites - 1, nr_sites)

#      # Left-compression
#      mpo_new = mpo + zero
#      mpo_new.compress(relerr=1e-6, method='var', direction='left')
#      assert_array_equal(mpo_new.bdims, bond_dim)
#      assert_array_almost_equal(mpo_to_global(mpo), mpo_to_global(mpo_new))
#      assert_correct_normalzation(mpo_new, 0, 1)

# FIXME
#  @pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
#  def test_compression_var_overlap(nr_sites, local_dim, bond_dim):
#      mpo = factory.random_mpa(nr_sites, (local_dim, local_dim), bond_dim)
#      mpo_new = mpo.copy()

#      # Catch superficious compression paramter
#      max_bdim = max(bond_dim // 2, 1)

#      overlap = mpo_new.compress(max_bdim=max_bdim, method='var', direction='right')
#      assert_almost_equal(overlap, mp.inner(mpo, mpo_new), decimal=5)
#      assert all(bdim <= max_bdim for bdim in mpo_new.bdims)

#      mpo_new = mpo.copy()
#      overlap = mpo_new.compress(max_bdim=max_bdim, method='var', direction='left')
#      assert_almost_equal(overlap, mp.inner(mpo, mpo_new), decimal=5)
#      assert all(bdim <= max_bdim for bdim in mpo_new.bdims)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_var_to_svd(nr_sites, local_dim, bond_dim):
    randstate = np.random.RandomState(seed=42)
    mpa = factory.random_mpo(nr_sites, local_dim, bond_dim,
                             randstate=randstate, normalized=True)
    array = mpa.to_array()
    target_bonddim = max(2 * bond_dim // 3, 1)

    right_svd_res = _svd_compression_full(mpa, 'right', target_bonddim)
    left_svd_res = _svd_compression_full(mpa, 'left', target_bonddim)
    right_svd_overlap = np.abs(np.vdot(array, right_svd_res))
    left_svd_overlap = np.abs(np.vdot(array, left_svd_res))

    # max_num_sweeps = 3 and 4 is sometimes not good enough.
    mpa = mpa.compress_var(num_sweeps=5, bdim=target_bonddim, randstate=randstate)
    mpa_compr_overlap = np.abs(np.vdot(array, mpa.to_array()))

    # The basic intuition is that variational compression, given
    # enough sweeps, should be at least as good as left and right SVD
    # compression because the SVD compression scheme has a strong
    # interdependence between truncations at the individual sites,
    # while variational compression does not have that. Therefore, we
    # check exactly that.

    overlap_rel_tol = 1e-6
    assert mpa_compr_overlap >= right_svd_overlap * (1 - overlap_rel_tol)
    assert mpa_compr_overlap >= left_svd_overlap * (1 - overlap_rel_tol)


@pt.mark.parametrize('nr_sites, local_dim, bond_dim', MP_TEST_PARAMETERS)
def test_compression_var_to_svd_twosite(nr_sites, local_dim, bond_dim):
    randstate = np.random.RandomState(seed=42)
    mpa = factory.random_mpo(nr_sites, local_dim, bond_dim,
                             randstate=randstate, normalized=True)
    array = mpa.to_array()
    target_bonddim = max(2 * bond_dim // 3, 1)

    right_svd_res = _svd_compression_full(mpa, 'right', target_bonddim)
    left_svd_res = _svd_compression_full(mpa, 'left', target_bonddim)
    right_svd_overlap = np.abs(np.vdot(array, right_svd_res))
    left_svd_overlap = np.abs(np.vdot(array, left_svd_res))

    # same as test_compression_var_to_svd, but with sweep_sites=2
    mpa = mpa.compress_var(num_sweeps=3, sweep_sites=2,
                           bdim=target_bonddim, randstate=randstate)
    mpa_compr_overlap = np.abs(np.vdot(array, mpa.to_array()))

    overlap_rel_tol = 1e-6
    assert mpa_compr_overlap >= right_svd_overlap * (1 - overlap_rel_tol)
    assert mpa_compr_overlap >= left_svd_overlap * (1 - overlap_rel_tol)


#######################################
#  Compression test helper functions  #
#######################################
def _svd_compression_full(mpa, direction, target_bonddim):
    """Re-implement what SVD compression on MPAs does but on the level of the
    full matrix representation, i.e. it truncates the Schmidt-decompostion
    on each bipartition sequentially.

    Two implementations that produce the same data are not a guarantee
    for correctness, but a check for consistency is nice anyway.

    :param mpa: The MPA to compress
    :param direction: 'right' means sweep from left to right,
        'left' vice versa
    :param target_bonddim: Compress to this bond dimension
    :returns: Result as numpy.ndarray

    """
    def singlecut(array, nr_left, plegs, target_bonddim):
        array_shape = array.shape
        array = array.reshape((np.prod(array_shape[:nr_left * plegs]), -1))
        u, s, v = svd(array)
        u = u[:, :target_bonddim]
        s = s[:target_bonddim]
        v = v[:target_bonddim, :]
        opt_compr = np.dot(u * s, v)
        opt_compr = opt_compr.reshape(array_shape)
        return opt_compr

    array = mpa.to_array()
    plegs = mpa.plegs[0]
    nr_sites = len(mpa)
    if direction == 'right':
        nr_left_values = range(1, nr_sites)
    else:
        nr_left_values = range(nr_sites-1, 0, -1)
    for nr_left in nr_left_values:
        array = singlecut(array, nr_left, plegs, target_bonddim)
    return array
