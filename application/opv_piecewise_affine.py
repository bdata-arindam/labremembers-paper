"""A transparent continuous response emulator for the measured OPV datasets.

The original measurements remain in separate source files. This interpolates
composition-group means. It does not simulate experimentally measured carryover.
Lipschitz bounds apply to this mathematical interpolant on its convex hull only.
"""
from __future__ import annotations
from fractions import Fraction
from pathlib import Path
import math
import numpy as np
import pandas as pd
from scipy.spatial import Delaunay, ConvexHull

HERE=Path(__file__).resolve().parent
FEATURES=['p3ht_fraction','second_donor_fraction','pcbm_fraction','oidtbr_fraction']
BASIS=np.array([[1/math.sqrt(2),1/math.sqrt(6),1/math.sqrt(12)],
                [-1/math.sqrt(2),1/math.sqrt(6),1/math.sqrt(12)],
                [0,-2/math.sqrt(6),1/math.sqrt(12)],
                [0,0,-3/math.sqrt(12)]])


def determinant3(a):
    a=np.asarray(a,dtype=np.int64)
    return (a[...,0,0]*(a[...,1,1]*a[...,2,2]-a[...,1,2]*a[...,2,1])
            -a[...,0,1]*(a[...,1,0]*a[...,2,2]-a[...,1,2]*a[...,2,0])
            +a[...,0,2]*(a[...,1,0]*a[...,2,1]-a[...,1,1]*a[...,2,0]))


def adjugate3(a):
    a=np.asarray(a,dtype=np.int64)
    return np.array([[a[1,1]*a[2,2]-a[1,2]*a[2,1],a[0,2]*a[2,1]-a[0,1]*a[2,2],a[0,1]*a[1,2]-a[0,2]*a[1,1]],
                     [a[1,2]*a[2,0]-a[1,0]*a[2,2],a[0,0]*a[2,2]-a[0,2]*a[2,0],a[0,2]*a[1,0]-a[0,0]*a[1,2]],
                     [a[1,0]*a[2,1]-a[1,1]*a[2,0],a[0,1]*a[2,0]-a[0,0]*a[2,1],a[0,0]*a[1,1]-a[0,1]*a[1,0]]],dtype=np.int64)


def upper_float(q):
    """A binary64 upper endpoint for an exact nonnegative rational."""
    out=float(q)
    while Fraction.from_float(out)<q:out=np.nextafter(out,math.inf)
    return float(np.nextafter(out,math.inf))


class PiecewiseAffineOPV:
    dimension=4
    def __init__(self,x,y,system='unspecified',compute_exact_bounds=True):
        self.system=system
        x=np.asarray(x,float);self.y=np.asarray(y,float)
        if x.ndim!=2 or x.shape[1]!=4 or self.y.shape!=(len(x),):raise ValueError('Expected X (n,4) and y (n,)')
        if not np.isfinite(x).all() or not np.isfinite(self.y).all():raise ValueError('Nonfinite source value')
        self.grid=np.rint(50*x).astype(np.int64)
        self.grid_snap_max=float(np.max(np.abs(x-self.grid/50)))
        if self.grid_snap_max>1e-12 or np.any(self.grid.sum(axis=1)!=50) or np.any(self.grid<0):raise ValueError('Source is not the declared 0.02 simplex grid')
        self.x=self.grid/50
        if len(np.unique(self.grid,axis=0))!=len(x):raise ValueError('Group exact duplicate compositions before fitting')
        self.z=self.x@BASIS
        self.tri=Delaunay(self.z,qhull_options='Qbb Qc Qz Q12')
        self.simplices=self.tri.simplices.copy()
        # Integer-grid determinant exactly identifies zero-volume numerical cells.
        integer_vertices=self.grid[self.simplices,:3]
        a=integer_vertices[:,1:,:]-integer_vertices[:,:1,:]
        det=determinant3(a)
        self.valid=det!=0
        self.zero_volume_count=int((~self.valid).sum())
        self.valid_ids=np.flatnonzero(self.valid)
        self.gradient4=np.full((len(det),4),np.nan)
        self.intercept=np.full(len(det),np.nan)
        for cell in self.valid_ids:
            ids=self.simplices[cell];dy=self.y[ids[1:]]-self.y[ids[0]]
            gradient=np.linalg.solve(a[cell]/50,dy)
            self.gradient4[cell,:3]=gradient;self.gradient4[cell,3]=0.
            self.intercept[cell]=self.y[ids[0]]-gradient@self.x[ids[0],:3]
        self.lipschitz_l1=float(np.max(np.ptp(self.gradient4[self.valid_ids],axis=1)/2))
        centered=self.gradient4[self.valid_ids]-self.gradient4[self.valid_ids].mean(axis=1,keepdims=True)
        self.lipschitz_l2=float(np.max(np.linalg.norm(centered,axis=1)))
        self.bound_arithmetic='binary64 gradients'
        self.l1_worst_cell=None;self.l2_worst_cell=None
        if compute_exact_bounds:
            # Binary64 response means are represented exactly as rational values.
            exact_y=[Fraction.from_float(float(v)) for v in self.y]
            max_l1=Fraction(0);max_l2sq=Fraction(0)
            for cell in self.valid_ids:
                ids=self.simplices[cell];adj=adjugate3(a[cell]);dd=int(det[cell])
                delta=[exact_y[int(i)]-exact_y[int(ids[0])] for i in ids[1:]]
                g=[sum((int(adj[j,k])*delta[k] for k in range(3)),Fraction(0))*50/dd for j in range(3)]+[Fraction(0)]
                l1=(max(g)-min(g))/2
                gm=sum(g,Fraction(0))/4
                l2sq=sum(((v-gm)**2 for v in g),Fraction(0))
                if l1>max_l1:max_l1=l1;self.l1_worst_cell=int(cell)
                if l2sq>max_l2sq:max_l2sq=l2sq;self.l2_worst_cell=int(cell)
            self.lipschitz_l1=upper_float(max_l1)
            l2=math.sqrt(float(max_l2sq))
            while Fraction.from_float(l2)**2<max_l2sq:l2=np.nextafter(l2,math.inf)
            self.lipschitz_l2=float(np.nextafter(l2,math.inf))
            self.exact_l1_fraction=str(max_l1)
            self.exact_l2_squared_fraction=str(max_l2sq)
            self.bound_arithmetic='Exact rational gradients on integer composition grid with exact binary64 response values; returned floats rounded upward'
        self.hull=ConvexHull(self.z)
        self.hull_volume=float(self.hull.volume)
        self.tetrahedron_volume_exact=Fraction(int(np.abs(det).sum()),3*50**3)
        self.has_all_pure_components=all(np.any(np.all(self.grid==50*v,axis=1)) for v in np.eye(4,dtype=int))
        if self.has_all_pure_components and self.tetrahedron_volume_exact!=Fraction(1,3):
            raise ValueError('Nondegenerate cells do not have exact full-simplex volume')
        if not np.isclose(float(self.tetrahedron_volume_exact),self.hull_volume,rtol=1e-9,atol=1e-12):
            raise ValueError('Tetrahedron volumes fail convex-hull coverage check')
        self.report={'system':system,'dimension':4,'n_compositions':len(self.x),'n_cells':len(det),
                     'n_positive_volume_cells':int(self.valid.sum()),'n_zero_volume_numerical_cells':self.zero_volume_count,
                     'grid_snap_max_abs':self.grid_snap_max,
                     'hull_volume':self.hull_volume,'exact_sum_cell_volumes':str(self.tetrahedron_volume_exact),
                     'full_simplex_hull':self.has_all_pure_components,'lipschitz_l1':self.lipschitz_l1,
                     'lipschitz_l2':self.lipschitz_l2,'bound_arithmetic':self.bound_arithmetic,
                     'minimum_absolute_integer_determinant':int(np.min(np.abs(det[self.valid]))),
                     'maximum_simplex_condition_number':float(max(np.linalg.cond(a[c]) for c in self.valid_ids)),
                     'l1_worst_cell':self.l1_worst_cell,'l2_worst_cell':self.l2_worst_cell}

    @classmethod
    def from_system(cls,system,**kwargs):
        data=pd.read_csv(HERE/f'{system}_hte_composition_means.csv',float_precision='round_trip')
        return cls(data[FEATURES].to_numpy(),data.degradation_mean.to_numpy(),system,**kwargs)

    def predict(self,x,strict=False):
        x=np.asarray(x,float);scalar=x.ndim==1
        flat=x.reshape(-1,4)
        if not np.isfinite(flat).all():raise ValueError('Nonfinite composition')
        if np.any(flat< -1e-10) or np.any(np.abs(flat.sum(axis=1)-1)>1e-10):raise ValueError('Composition outside unit simplex')
        z=flat@BASIS
        cell=self.tri.find_simplex(z,tol=1e-10)
        result=np.full(len(flat),np.nan)
        inside=cell>=0
        safe=inside.copy();safe[inside]=self.valid[cell[inside]]
        if safe.any():result[safe]=np.einsum('ij,ij->i',self.gradient4[cell[safe]],flat[safe])+self.intercept[cell[safe]]
        # Boundary numerical ties: use a valid cell's barycentric coordinates,
        # never nearest-neighbor values or extrapolation from outside the hull.
        for i in np.flatnonzero(inside&~safe):
            for c in self.valid_ids:
                ids=self.simplices[c]
                w=np.linalg.solve((self.x[ids[1:],:3]-self.x[ids[0],:3]).T,flat[i,:3]-self.x[ids[0],:3])
                bary=np.r_[1-w.sum(),w]
                if bary.min()>=-1e-10 and bary.max()<=1+1e-10:
                    result[i]=float(bary@self.y[ids]);break
        if strict and not np.isfinite(result).all():raise ValueError('Query outside training convex hull; extrapolation forbidden')
        return float(result[0]) if scalar else result.reshape(x.shape[:-1])

    def __call__(self,x):return self.predict(x,strict=True)
