from ome.base import *

from sqlalchemy.orm import relationship, backref
from sqlalchemy import Table, MetaData, create_engine, Column, Integer, \
    String, Float, ForeignKey, select, Boolean
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.schema import UniqueConstraint,PrimaryKeyConstraint

import simplejson as json


class Gene(GenomeRegion):
    __tablename__ = 'gene'

    id = Column(Integer,
                ForeignKey('genome_region.id', onupdate="CASCADE", ondelete="CASCADE"),
                primary_key=True)
    info = Column(String(300))
    name = Column(String)
    locus_tag = Column(String)
    mapped_to_genbank = Column(Boolean)
    alternative_transcript_of = Column(Integer,
                                       ForeignKey('gene.id'),
                                       nullable=True)

    __mapper_args__ = { 'polymorphic_identity': 'gene' }

    def __repr__(self):
        return '<ome Gene(id=%d, bigg_id=%s, name=%s)>' % (self.id, self.bigg_id,
                                                         self.name)

    def __init__(self, bigg_id, leftpos=None, rightpos=None,
                 mapped_to_genbank=False, strand=None, chromosome_id=None,
                 info=None, name=None, alternative_transcript_of=None, 
                 locus_tag=None):

        super(Gene, self).__init__(bigg_id=bigg_id, chromosome_id=chromosome_id,
                                   leftpos=leftpos, rightpos=rightpos, strand=strand)
        self.name = name
        self.info = info
        self.mapped_to_genbank = mapped_to_genbank
        self.alternative_transcript_of = alternative_transcript_of
        self.locus_tag = locus_tag


class Motif(GenomeRegion):
    __tablename__ = 'motif'

    id = Column(Integer, ForeignKey('genome_region.id'), primary_key=True)
    pval = Column(Float)

    bound_component_id = Column(Integer, ForeignKey('component.id'))
    bound_component = relationship("Component")

    def __repr__(self):
        return "Motif (%s) %d-%d %s %5.2f"% \
            (self.bound_component.name, self.leftpos, self.rightpos,\
                                 self.strand, self.pval)

    def __init__(self, bigg_id, leftpos, rightpos, strand, pval=None, info=None):
        super(Motif, self).__init__(bigg_id=bigg_id, leftpos=leftpos,
                                    rightpos=rightpos, strand=strand,
                                    chromosome_id=chromosome_id)
        self.pval = pval
        self.info = info


class ComplexComposition(Base):
    __tablename__ = 'complex_composition'

    complex_id = Column(Integer, ForeignKey('complex.id'), primary_key=True)
    component_id = Column(Integer, ForeignKey('component.id'), primary_key=True)
    stoichiometry = Column(Integer)

    __table_args__ = (UniqueConstraint('complex_id','component_id'),{})

    def __init__(self, complex_id, component_id, stoichiometry):
        self.complex_id = complex_id
        self.component_id = component_id
        self.stoichiometry = stoichiometry


class Complex(Component):
    __tablename__ = 'complex'

    __mapper_args__ = {'polymorphic_identity': 'complex'}

    id = Column(Integer, ForeignKey('component.id'), primary_key=True)

    children = relationship("Component", secondary="complex_composition",
                            primaryjoin = id == ComplexComposition.complex_id,
                            backref="parent")

    @hybrid_property
    def all_children(self):
        session = Session()
        included_components = (session
                               .query(ComplexComposition.complex_id, ComplexComposition.component_id)
                               .filter(ComplexComposition.complex_id==self.id)
                               .cte(name="included_components", recursive=True))

        incl_alias = aliased(included_components, name="incl_cplx")
        complex_alias = aliased(ComplexComposition, name="cplx")
        included_components = (included_components
                               .union_all(session
                                          .query(complex_alias.complex_id, complex_alias.component_id)
                                          .filter(complex_alias.complex_id==incl_alias.c.component_id)))

        return (session
                .query(Component)
                .join(included_components,
                      Component.id==included_components.c.component_id)
                .all())

    def __init__(self, bigg_id, name):
        super(Complex, self).__init__(bigg_id, name)

    def __repr__(self):
        return "Complex (#%d):  %s" % \
            (self.id, self.bigg_id)


class DNA(Component):
    __tablename__ = 'dna'

    id = Column(Integer, ForeignKey('component.id'), primary_key=True)

    genome_region_id = Column(Integer, ForeignKey('genome_region.id'))
    genome_region = relationship('GenomeRegion', backref=backref('dna', lazy='dynamic'))
    dna_type = Column(String(20))

    __mapper_args__ = {
        'polymorphic_identity': 'dna',
        'polymorphic_on': dna_type
    }

    def __init__(self, bigg_id, name, leftpos=None, rightpos=None, strand=None, chromosome_id=None):
        super(DNA, self).__init__(bigg_id, name)
        session = Session()
        self.genome_region_id = session.get_or_create(GenomeRegion, name=name,
                                                      leftpos=leftpos,
                                                      rightpos=rightpos,
                                                      chromosome_id=chromosome_id,
                                                      strand=strand).id
        session.close()

    def __repr__(self):
        return ("DNA (#%d, %s) %d-%d %s" % (self.id, self.bigg_id,
                                            self.genome_region.leftpos,
                                            self.genome_region.rightpos,
                                            self.genome_region.strand))


class DnaBindingSite(DNA):
    __tablename__ = 'dna_binding_site'

    id = Column(Integer, ForeignKey('dna.id'), primary_key=True)
    centerpos = Column(Integer)
    width = Column(Integer)

    __mapper_args__ = { 'polymorphic_identity': 'binding_site' }

    def __init__(self, name, leftpos, rightpos, strand, chromosome_id, centerpos, width):
        super(DnaBindingSite, self).__init__(name, leftpos, rightpos, strand, chromosome_id)
        self.centerpos = centerpos
        self.width = width


class RNA(Component):
    __tablename__ = 'rna'

    id = Column(Integer, ForeignKey('component.id'), primary_key=True)

    genome_region_id = Column(Integer, ForeignKey('genome_region.id'))

    __mapper_args__ = { 'polymorphic_identity': 'rna' }

    def __init__(self, bigg_id, name, leftpos=None, rightpos=None, strand=None, chromosome_id=None):
        super(RNA, self).__init__(bigg_id, name)
        session = Session()
        self.genome_region_id = session.get_or_create(GenomeRegion, name=name, leftpos=leftpos,\
                                                      rightpos=rightpos, strand=strand,
                                                      chromosome_id=chromosome_id).id
        session.close()

    def __repr__(self):
        return "RNA (#%d, %s)" % \
            (self.id, self.bigg_id)


class TUGenes(Base):
    __tablename__ = 'tu_genes'

    tu_id = Column(Integer, ForeignKey('tu.id'), primary_key=True)
    gene_id = Column(Integer, ForeignKey('gene.id'), primary_key=True)

    __table_args__ = (UniqueConstraint('tu_id','gene_id'),{})

    def __init__(self, tu_id, gene_id):
        self.tu_id = tu_id
        self.gene_id = gene_id


class TU(RNA):
    __tablename__ = 'tu'

    id = Column(Integer, ForeignKey('rna.id'), primary_key=True)
    genome_region = relationship("GenomeRegion")
    genes = relationship("Gene", secondary="tu_genes", backref="tu",
                         primaryjoin=(id == TUGenes.tu_id))

    __mapper_args__ = { 'polymorphic_identity': 'tu' }

    """
    @hybrid_property
    def tss(self):
        if self.genome_region.strand == '+':
            return self.genome_region.leftpos
        else:
            return self.genome_region.rightpos
    """

    def __init__(self, name, leftpos, rightpos, strand, genome_id):
        super(TU, self).__init__(name, leftpos, rightpos, strand, genome_id)

    def __repr__(self):
        return "TU (#%d, %s)" % \
            (self.id, self.name)


class Protein(Component):
    __tablename__ = 'protein'

    __mapper_args__ = { 'polymorphic_identity': 'protein' }

    id = Column(Integer, ForeignKey('component.id'), primary_key=True)
    gene_id = Column(Integer, ForeignKey('gene.id'))
    gene = relationship('Gene', backref='protein')

    def __init__(self, bigg_id, name, gene_id=None):
        super(Protein, self).__init__(bigg_id, name)
        self.gene_id = gene_id
        
    def __repr__(self):
        return "Protein (#%d, %s)" % \
            (self.id, self.bigg_id)


class Metabolite(Component):
    __tablename__ = 'metabolite'

    __mapper_args__ = { 'polymorphic_identity': 'metabolite' }

    id = Column(Integer,
                ForeignKey('component.id', onupdate="CASCADE", ondelete="CASCADE"),
                primary_key=True)

    formula = Column(String, nullable=True)
    smiles = Column(String(200), nullable=True)
    charge = Column(Integer, nullable=True)

    def __init__(self, bigg_id, name, formula, charge=None, smiles=None):
        super(Metabolite, self).__init__(bigg_id, name)
        self.charge = charge
        self.formula = formula
        self.smiles = smiles


    def __repr__(self):
        return "Small Molecule (#%d, %s)" % (self.id, self.bigg_id)


class GeneGrouping(Base):
    __tablename__ = 'gene_grouping'

    group_id = Column(Integer, ForeignKey('gene_group.id'), primary_key=True)
    gene_id = Column(Integer, ForeignKey('gene.id'), primary_key=True)

    __table_args__ = (UniqueConstraint('group_id','gene_id'),{})

    def __init__(self, group_id, gene_id):
        self.group_id = group_id
        self.gene_id = gene_id

class GeneGroup(Base):
    __tablename__ = 'gene_group'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))

    genes = relationship("Gene", secondary="gene_grouping",\
                                 primaryjoin = id == GeneGrouping.group_id,\
                                 backref="groups")

    __table_args__ = (UniqueConstraint('name'),{})

    def __repr__(self):
        return "Gene Group (#%d, %s): %s" % \
            (self.id, self.name, ', '.join([g.name for g in self.genes]))

    def __init__(self, name):
        self.name = name







